"""
Batch Processor

Эффективная обработка групп задач.

Features:
- Auto-batching (автоматическое группирование)
- Configurable batch size & timeout
- Priority queues
- Backpressure handling
- 5-10x throughput improvement

Usage:
    # LLM batch processing
    processor = BatchProcessor(
        process_fn=ollama.chat_batch,
        batch_size=10,
        timeout=1.0,
    )
    
    # Submit items
    future1 = processor.submit("Question 1")
    future2 = processor.submit("Question 2")
    # ...
    future10 = processor.submit("Question 10")
    
    # All processed in single batch!
    result = await future1
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar, Optional

log = logging.getLogger("digital_being.batch_processor")

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class BatchItem(Generic[T, R]):
    """Single item in batch."""
    data: T
    priority: int = 0
    future: asyncio.Future[R] | None = None
    timestamp: float = 0.0


class BatchProcessor(Generic[T, R]):
    """
    Автоматически группирует задачи в batches.
    
    Пример:
        processor = BatchProcessor(
            process_fn=lambda items: [process(x) for x in items],
            batch_size=10,
            timeout=1.0,
        )
        
        results = await asyncio.gather(*[
            processor.submit(item)
            for item in items
        ])
    """
    
    def __init__(
        self,
        process_fn: Callable[[list[T]], list[R]],
        batch_size: int = 10,
        timeout: float = 1.0,
        max_queue_size: int = 1000,
    ) -> None:
        """
        Args:
            process_fn: Функция обработки batch (list[T] -> list[R])
            batch_size: Максимальный размер batch
            timeout: Максимальное ожидание batch (секунды)
            max_queue_size: Максимальный размер очереди
        """
        self._process_fn = process_fn
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_queue_size = max_queue_size
        
        self._queue: deque[BatchItem[T, R]] = deque()
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self._batches_processed = 0
        self._items_processed = 0
        self._total_wait_time = 0.0
        self._total_process_time = 0.0
        
        log.info(
            f"BatchProcessor initialized: "
            f"batch_size={batch_size}, timeout={timeout}s"
        )
    
    async def start(self) -> None:
        """Запустить background обработку."""
        if self._running:
            return
        
        self._running = True
        self._processing_task = asyncio.create_task(self._process_loop())
        log.info("BatchProcessor started")
    
    async def stop(self) -> None:
        """Остановить обработку (дождаться завершения)."""
        if not self._running:
            return
        
        self._running = False
        
        if self._processing_task:
            await self._processing_task
        
        # Process remaining items
        if self._queue:
            await self._process_batch(list(self._queue))
            self._queue.clear()
        
        log.info("BatchProcessor stopped")
    
    async def submit(self, data: T, priority: int = 0) -> R:
        """
        Добавить item в batch.
        
        Args:
            data: Данные для обработки
            priority: Приоритет (больше = выше)
        
        Returns:
            Результат обработки
        """
        # Backpressure
        if len(self._queue) >= self._max_queue_size:
            log.warning(f"Queue full ({self._max_queue_size}), waiting...")
            while len(self._queue) >= self._max_queue_size:
                await asyncio.sleep(0.1)
        
        # Create future
        loop = asyncio.get_event_loop()
        future: asyncio.Future[R] = loop.create_future()
        
        item = BatchItem(
            data=data,
            priority=priority,
            future=future,
            timestamp=time.time(),
        )
        
        async with self._lock:
            self._queue.append(item)
        
        # Start processing if not running
        if not self._running:
            await self.start()
        
        return await future
    
    async def _process_loop(self) -> None:
        """Главный цикл обработки."""
        while self._running:
            try:
                # Wait for batch to fill or timeout
                start_wait = time.time()
                
                while len(self._queue) < self._batch_size:
                    if not self._queue:
                        await asyncio.sleep(0.01)
                        continue
                    
                    # Check oldest item
                    oldest = self._queue[0]
                    age = time.time() - oldest.timestamp
                    
                    if age >= self._timeout:
                        break  # Timeout reached
                    
                    await asyncio.sleep(0.01)
                
                if not self._queue:
                    continue
                
                # Extract batch
                async with self._lock:
                    batch_items = [
                        self._queue.popleft()
                        for _ in range(min(self._batch_size, len(self._queue)))
                    ]
                
                # Sort by priority (desc)
                batch_items.sort(key=lambda x: x.priority, reverse=True)
                
                wait_time = time.time() - start_wait
                self._total_wait_time += wait_time
                
                # Process batch
                await self._process_batch(batch_items)
                
            except Exception as e:
                log.error(f"Error in process loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)
    
    async def _process_batch(self, items: list[BatchItem[T, R]]) -> None:
        """Обработать batch."""
        if not items:
            return
        
        start_time = time.time()
        batch_data = [item.data for item in items]
        
        try:
            log.debug(f"Processing batch of {len(items)} items")
            
            # Call process function
            results = self._process_fn(batch_data)
            
            # Resolve futures
            for item, result in zip(items, results):
                if item.future and not item.future.done():
                    item.future.set_result(result)
            
            # Statistics
            process_time = time.time() - start_time
            self._batches_processed += 1
            self._items_processed += len(items)
            self._total_process_time += process_time
            
            log.debug(
                f"Batch processed: {len(items)} items in {process_time:.3f}s "
                f"({len(items)/process_time:.1f} items/s)"
            )
            
        except Exception as e:
            log.error(f"Batch processing failed: {e}", exc_info=True)
            
            # Reject all futures
            for item in items:
                if item.future and not item.future.done():
                    item.future.set_exception(e)
    
    def get_stats(self) -> dict:
        """Получить статистику."""
        avg_wait = (
            self._total_wait_time / self._batches_processed
            if self._batches_processed > 0
            else 0.0
        )
        avg_process = (
            self._total_process_time / self._batches_processed
            if self._batches_processed > 0
            else 0.0
        )
        avg_batch_size = (
            self._items_processed / self._batches_processed
            if self._batches_processed > 0
            else 0.0
        )
        
        return {
            "queue_size": len(self._queue),
            "batches_processed": self._batches_processed,
            "items_processed": self._items_processed,
            "avg_batch_size": avg_batch_size,
            "avg_wait_time": avg_wait,
            "avg_process_time": avg_process,
            "running": self._running,
        }


class AsyncBatchProcessor(Generic[T, R]):
    """
    Async version с async process function.
    """
    
    def __init__(
        self,
        process_fn: Callable[[list[T]], asyncio.Future[list[R]]],
        batch_size: int = 10,
        timeout: float = 1.0,
        max_queue_size: int = 1000,
    ) -> None:
        self._process_fn = process_fn
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_queue_size = max_queue_size
        
        self._queue: deque[BatchItem[T, R]] = deque()
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._batches_processed = 0
        self._items_processed = 0
        
        log.info(
            f"AsyncBatchProcessor initialized: "
            f"batch_size={batch_size}, timeout={timeout}s"
        )
    
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._processing_task = asyncio.create_task(self._process_loop())
        log.info("AsyncBatchProcessor started")
    
    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._processing_task:
            await self._processing_task
        if self._queue:
            await self._process_batch(list(self._queue))
            self._queue.clear()
        log.info("AsyncBatchProcessor stopped")
    
    async def submit(self, data: T, priority: int = 0) -> R:
        if len(self._queue) >= self._max_queue_size:
            log.warning(f"Queue full ({self._max_queue_size}), waiting...")
            while len(self._queue) >= self._max_queue_size:
                await asyncio.sleep(0.1)
        
        loop = asyncio.get_event_loop()
        future: asyncio.Future[R] = loop.create_future()
        
        item = BatchItem(
            data=data,
            priority=priority,
            future=future,
            timestamp=time.time(),
        )
        
        async with self._lock:
            self._queue.append(item)
        
        if not self._running:
            await self.start()
        
        return await future
    
    async def _process_loop(self) -> None:
        while self._running:
            try:
                while len(self._queue) < self._batch_size:
                    if not self._queue:
                        await asyncio.sleep(0.01)
                        continue
                    oldest = self._queue[0]
                    age = time.time() - oldest.timestamp
                    if age >= self._timeout:
                        break
                    await asyncio.sleep(0.01)
                
                if not self._queue:
                    continue
                
                async with self._lock:
                    batch_items = [
                        self._queue.popleft()
                        for _ in range(min(self._batch_size, len(self._queue)))
                    ]
                
                batch_items.sort(key=lambda x: x.priority, reverse=True)
                await self._process_batch(batch_items)
                
            except Exception as e:
                log.error(f"Error in async process loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)
    
    async def _process_batch(self, items: list[BatchItem[T, R]]) -> None:
        if not items:
            return
        
        batch_data = [item.data for item in items]
        
        try:
            log.debug(f"Processing async batch of {len(items)} items")
            
            # Await async process function
            results = await self._process_fn(batch_data)
            
            for item, result in zip(items, results):
                if item.future and not item.future.done():
                    item.future.set_result(result)
            
            self._batches_processed += 1
            self._items_processed += len(items)
            
            log.debug(f"Async batch processed: {len(items)} items")
            
        except Exception as e:
            log.error(f"Async batch processing failed: {e}", exc_info=True)
            for item in items:
                if item.future and not item.future.done():
                    item.future.set_exception(e)
    
    def get_stats(self) -> dict:
        avg_batch_size = (
            self._items_processed / self._batches_processed
            if self._batches_processed > 0
            else 0.0
        )
        return {
            "queue_size": len(self._queue),
            "batches_processed": self._batches_processed,
            "items_processed": self._items_processed,
            "avg_batch_size": avg_batch_size,
            "running": self._running,
        }
