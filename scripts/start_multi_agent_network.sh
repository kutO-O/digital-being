#!/bin/bash

# Start a test network of 3 agents

echo "Starting Multi-Agent Network..."
echo "================================"

# Create storage directories
mkdir -p memory/agents/alice
mkdir -p memory/agents/bob
mkdir -p memory/agents/charlie

# Start Alice (Research)
echo "Starting Alice (Research Agent) on port 9000..."
python main.py \
  --agent-name alice \
  --specialization research \
  --port 9000 \
  --storage memory/agents/alice &
ALICE_PID=$!

# Start Bob (Coding)
echo "Starting Bob (Coding Agent) on port 9001..."
python main.py \
  --agent-name bob \
  --specialization coding \
  --port 9001 \
  --storage memory/agents/bob &
BOB_PID=$!

# Start Charlie (Testing)
echo "Starting Charlie (Testing Agent) on port 9002..."
python main.py \
  --agent-name charlie \
  --specialization testing \
  --port 9002 \
  --storage memory/agents/charlie &
CHARLIE_PID=$!

echo ""
echo "Network started!"
echo "  Alice   (Research): PID $ALICE_PID"
echo "  Bob     (Coding):   PID $BOB_PID"
echo "  Charlie (Testing):  PID $CHARLIE_PID"
echo ""
echo "Press Ctrl+C to stop all agents"

# Trap Ctrl+C and kill all agents
trap "echo ''; echo 'Stopping agents...'; kill $ALICE_PID $BOB_PID $CHARLIE_PID; exit" INT

# Wait
wait
