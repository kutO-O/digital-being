# This file contains the reference for full heavy_tick.py implementation
# Copy the methods from cite:52 and add _step_social_interaction() and _build_social_context()
# from the previous commit (bdf3b8ef157601355d8715fda9901cca103fe025)

# The file was too large to upload in one request.
# Please manually merge:
# 1. Take full heavy_tick.py from commit 72a0fb4113cdea61ecb08cb096a3c93c9b6d54a0
# 2. Add social_layer parameter to __init__()
# 3. Add self._social = social_layer
# 4. Add these two imports:
#    from core.social_layer import SocialLayer  # Stage 23
# 5. Add this line in _run_tick() after _step_time_perception():
#    await self._step_social_interaction(n)  # Stage 23
# 6. Add _step_social_interaction() method from bdf3b8ef
# 7. Add _build_social_context() method from bdf3b8ef
# 8. Update docstring to mention Stage 23 and hour_of_day parsing note
