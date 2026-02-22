"""
Digital Being — Semantic Memory System
Stage 29: Long-term knowledge and concept storage.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.semantic_memory")

class SemanticMemory:
    """
    Manages semantic (factual/conceptual) memory.
    
    Separate from episodic memory:
    - Episodic: "What happened" (events, experiences)
    - Semantic: "What I know" (facts, concepts, relationships)
    
    Features:
    - Concept storage
    - Relationship mapping
    - Fact extraction
    - Knowledge retrieval
    """
    
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path / "semantic_memory.json"
        
        self._state = {
            "concepts": {},  # concept_id -> {name, type, properties, confidence}
            "relationships": [],  # {from, to, type, strength}
            "facts": [],  # {fact, sources, confidence, timestamp}
            "total_knowledge_items": 0,
        }
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load semantic memory state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info("SemanticMemory: loaded state")
            except Exception as e:
                log.error(f"SemanticMemory: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save semantic memory state"""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"SemanticMemory: failed to save state: {e}")
    
    def add_concept(
        self,
        name: str,
        concept_type: str,
        properties: dict | None = None,
        confidence: float = 0.8
    ) -> str:
        """
        Add a concept to semantic memory.
        
        Args:
            name: Concept name
            concept_type: Type (entity, skill, tool, pattern, etc.)
            properties: Additional properties
            confidence: Confidence in concept (0-1)
        
        Returns:
            Concept ID
        """
        concept_id = f"{concept_type}_{name.lower().replace(' ', '_')}"
        
        # Check if exists
        if concept_id in self._state["concepts"]:
            # Update existing
            existing = self._state["concepts"][concept_id]
            existing["confidence"] = max(existing["confidence"], confidence)
            existing["last_updated"] = time.time()
            if properties:
                existing["properties"].update(properties)
        else:
            # Create new
            self._state["concepts"][concept_id] = {
                "id": concept_id,
                "name": name,
                "type": concept_type,
                "properties": properties or {},
                "confidence": confidence,
                "created_at": time.time(),
                "last_updated": time.time(),
                "access_count": 0
            }
            self._state["total_knowledge_items"] += 1
        
        self._save_state()
        
        log.debug(f"SemanticMemory: added concept '{name}' ({concept_type})")
        
        return concept_id
    
    def add_relationship(
        self,
        from_concept: str,
        to_concept: str,
        relationship_type: str,
        strength: float = 0.8
    ) -> None:
        """
        Add relationship between concepts.
        
        Args:
            from_concept: Source concept ID
            to_concept: Target concept ID
            relationship_type: Type (is_a, uses, relates_to, etc.)
            strength: Relationship strength (0-1)
        """
        # Check if relationship exists
        for rel in self._state["relationships"]:
            if (rel["from"] == from_concept and 
                rel["to"] == to_concept and 
                rel["type"] == relationship_type):
                # Update strength
                rel["strength"] = max(rel["strength"], strength)
                rel["last_updated"] = time.time()
                self._save_state()
                return
        
        # Create new relationship
        self._state["relationships"].append({
            "from": from_concept,
            "to": to_concept,
            "type": relationship_type,
            "strength": strength,
            "created_at": time.time(),
            "last_updated": time.time()
        })
        
        self._save_state()
        
        log.debug(
            f"SemanticMemory: added relationship {from_concept} --[{relationship_type}]--> {to_concept}"
        )
    
    def add_fact(
        self,
        fact: str,
        source: str,
        confidence: float = 0.8
    ) -> None:
        """
        Add a fact to semantic memory.
        
        Args:
            fact: Fact statement
            source: Source of fact (episode_id, external, etc.)
            confidence: Confidence in fact
        """
        # Check if fact exists
        for existing_fact in self._state["facts"]:
            if existing_fact["fact"].lower() == fact.lower():
                # Update
                if source not in existing_fact["sources"]:
                    existing_fact["sources"].append(source)
                existing_fact["confidence"] = max(existing_fact["confidence"], confidence)
                self._save_state()
                return
        
        # Create new fact
        self._state["facts"].append({
            "fact": fact,
            "sources": [source],
            "confidence": confidence,
            "timestamp": time.time()
        })
        
        self._state["total_knowledge_items"] += 1
        self._save_state()
        
        log.debug(f"SemanticMemory: added fact '{fact[:50]}...'")
    
    def extract_knowledge_from_episode(self, episode: dict) -> None:
        """
        Extract semantic knowledge from episodic memory.
        
        Args:
            episode: Episode dict
        """
        event_type = episode.get("event_type", "")
        description = episode.get("description", "")
        episode_id = episode.get("id", "unknown")
        
        # Extract based on event type
        if event_type == "skill_learned":
            # Extract skill concept
            skill_name = self._extract_skill_name(description)
            if skill_name:
                concept_id = self.add_concept(
                    name=skill_name,
                    concept_type="skill",
                    properties={"learned_from": episode_id},
                    confidence=0.8
                )
                
                # Add fact
                self.add_fact(
                    f"Learned skill: {skill_name}",
                    source=episode_id,
                    confidence=0.8
                )
        
        elif event_type == "goal_achieved":
            # Extract goal concept and success pattern
            goal_name = self._extract_goal_name(description)
            if goal_name:
                concept_id = self.add_concept(
                    name=goal_name,
                    concept_type="goal",
                    properties={"status": "achieved", "episode": episode_id},
                    confidence=0.9
                )
                
                self.add_fact(
                    f"Successfully achieved: {goal_name}",
                    source=episode_id,
                    confidence=0.9
                )
        
        elif event_type == "insight":
            # Extract insight as fact
            self.add_fact(
                description,
                source=episode_id,
                confidence=0.85
            )
        
        elif "error" in event_type.lower():
            # Extract error pattern
            error_type = self._extract_error_type(description)
            if error_type:
                concept_id = self.add_concept(
                    name=error_type,
                    concept_type="error_pattern",
                    properties={"example": description[:100]},
                    confidence=0.7
                )
    
    def _extract_skill_name(self, description: str) -> str | None:
        """Extract skill name from description."""
        # Simple extraction - look for patterns
        if "learned" in description.lower():
            # Try to extract what was learned
            parts = description.lower().split("learned")
            if len(parts) > 1:
                skill = parts[1].strip().split()[0:3]  # First 3 words
                return " ".join(skill)
        return None
    
    def _extract_goal_name(self, description: str) -> str | None:
        """Extract goal name from description."""
        # Simple extraction
        if "goal" in description.lower():
            parts = description.split(":")
            if len(parts) > 1:
                return parts[1].strip()[:50]
        return description[:50]
    
    def _extract_error_type(self, description: str) -> str | None:
        """Extract error type from description."""
        common_errors = ["FileNotFoundError", "ValueError", "TypeError", "ImportError"]
        for error in common_errors:
            if error.lower() in description.lower():
                return error
        return "UnknownError"
    
    def get_concept(self, concept_id: str) -> dict | None:
        """Get concept by ID."""
        concept = self._state["concepts"].get(concept_id)
        if concept:
            concept["access_count"] += 1
            self._save_state()
        return concept
    
    def search_concepts(self, query: str, concept_type: str | None = None) -> list[dict]:
        """Search concepts by name or type."""
        results = []
        query_lower = query.lower()
        
        for concept_id, concept in self._state["concepts"].items():
            # Type filter
            if concept_type and concept["type"] != concept_type:
                continue
            
            # Name match
            if query_lower in concept["name"].lower():
                results.append(concept)
        
        # Sort by confidence and access count
        results.sort(key=lambda c: (c["confidence"], c["access_count"]), reverse=True)
        
        return results
    
    def get_related_concepts(self, concept_id: str, max_depth: int = 2) -> list[dict]:
        """Get concepts related to given concept."""
        related = set()
        to_explore = {concept_id}
        explored = set()
        
        for depth in range(max_depth):
            current_level = to_explore - explored
            if not current_level:
                break
            
            for cid in current_level:
                explored.add(cid)
                
                # Find relationships
                for rel in self._state["relationships"]:
                    if rel["from"] == cid:
                        related.add(rel["to"])
                        to_explore.add(rel["to"])
                    elif rel["to"] == cid:
                        related.add(rel["from"])
                        to_explore.add(rel["from"])
        
        # Get concept details
        return [self._state["concepts"][cid] for cid in related if cid in self._state["concepts"]]
    
    def get_facts_about(self, keyword: str) -> list[dict]:
        """Get facts containing keyword."""
        keyword_lower = keyword.lower()
        return [
            fact for fact in self._state["facts"]
            if keyword_lower in fact["fact"].lower()
        ]
    
    def get_stats(self) -> dict:
        """Get semantic memory statistics."""
        concept_types = {}
        for concept in self._state["concepts"].values():
            ctype = concept["type"]
            concept_types[ctype] = concept_types.get(ctype, 0) + 1
        
        return {
            "total_concepts": len(self._state["concepts"]),
            "total_relationships": len(self._state["relationships"]),
            "total_facts": len(self._state["facts"]),
            "total_knowledge_items": self._state["total_knowledge_items"],
            "concept_types": concept_types
        }
