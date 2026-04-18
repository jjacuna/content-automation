"""
services/kie_ai.py — Image + Video Generation via Kie.ai
==========================================================
Image: Nano Banana Pro — fast AI image generation
Video: Veo 3.1 — AI video generation (longer processing)

Students learn: async/polling APIs. These APIs don't return results instantly.
You create a task, then poll for the result. The X-ray shows every poll cycle.
"""

import os
import time
import requests

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
KIE_BASE_URL = "https://api.kie.ai/api/v1"
TASK_CREATE_URL = f"{KIE_BASE_URL}/jobs/createTask"
TASK_STATUS_URL = f"{KIE_BASE_URL}/jobs/recordInfo"
VIDEO_CREATE_URL = f"{KIE_BASE_URL}/veo/generate"
VIDEO_STATUS_URL = f"{KIE_BASE_URL}/veo/get-1080p-video"


def _get_headers():
    """Build auth headers for Kie.ai API."""
    api_key = os.getenv("KIE_API_KEY")
    if not api_key:
        return None
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


# ---------------------------------------------------------------------------
# generate_image() — Create an image with Nano Banana Pro
# ---------------------------------------------------------------------------
def generate_image(prompt, emit_event=None):
    """
    Generate an image using Kie.ai's Nano Banana Pro model.

    This is an ASYNC API pattern:
    1. POST to create a task → get a task_id
    2. GET to poll the task status every 2 seconds
    3. When status is "success", download the result

    Students see every poll cycle in the X-ray log.

    Args:
        prompt: Image description prompt
        emit_event: Callback for SSE logging (THIS IS KEY for the X-ray)

    Returns:
        dict with: image_url, task_id, duration, cost
    """
    emit = emit_event or (lambda *a, **kw: None)
    headers = _get_headers()

    if not headers:
        emit("image", "progress", "No KIE_API_KEY — returning demo image")
        return {
            "image_url": "https://placehold.co/1024x1024/17181C/C7A35A?text=Demo+Image",
            "task_id": "demo_task",
            "duration": 0,
            "cost": 0.0,
            "demo": True
        }

    # -- Step 1: Create the task --
    emit("image", "progress", "Creating image task on Kie.ai...")

    try:
        create_response = requests.post(
            TASK_CREATE_URL,
            headers=headers,
            json={
                "model": "google/nano-banana-pro",
                "input": {
                    "prompt": prompt,
                    "image_size": "1024x1024"
                }
            },
            timeout=30
        )
        create_response.raise_for_status()
        create_data = create_response.json()

        task_id = create_data.get("taskId") or create_data.get("task_id")
        if not task_id:
            raise Exception(f"No task_id in response: {create_data}")

        emit("image", "progress", f"Task created: {task_id}")

    except requests.exceptions.RequestException as e:
        emit("image", "error", f"Failed to create image task: {str(e)}")
        raise

    # -- Step 2: Poll for completion --
    # Images poll every 2 seconds, timeout after 120 seconds
    start_time = time.time()
    poll_interval = 2
    timeout = 120
    attempt = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            emit("image", "error", f"Image generation timed out after {timeout}s")
            raise Exception(f"Image generation timed out after {timeout} seconds")

        attempt += 1
        time.sleep(poll_interval)

        try:
            status_response = requests.get(
                TASK_STATUS_URL,
                headers=headers,
                params={"taskId": task_id},
                timeout=15
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            state = status_data.get("state", "unknown")

            # -- Emit polling events (the X-ray magic!) --
            emit("image", "polling",
                 f"Polling... attempt {attempt}, status: {state}",
                 {"attempt": attempt, "state": state, "elapsed": round(elapsed, 1)})

            if state == "success":
                # Extract the image URL from results
                results = status_data.get("results", {})
                image_url = results.get("url") or results.get("image_url", "")

                duration = round(time.time() - start_time, 1)
                cost = 0.09  # Approximate cost per image

                emit("image", "progress",
                     f"Complete! Image ready in {duration}s")

                return {
                    "image_url": image_url,
                    "task_id": task_id,
                    "duration": duration,
                    "cost": cost,
                    "demo": False
                }

            elif state in ("failed", "error"):
                error_msg = status_data.get("error", "Unknown error")
                emit("image", "error", f"Image generation failed: {error_msg}")
                raise Exception(f"Image generation failed: {error_msg}")

            # Otherwise keep polling (state is 'processing', 'pending', etc.)

        except requests.exceptions.RequestException as e:
            emit("image", "progress", f"Poll request failed (attempt {attempt}), retrying...")
            # Don't raise — just retry on the next poll cycle


# ---------------------------------------------------------------------------
# generate_video() — Create a video with Veo 3.1
# ---------------------------------------------------------------------------
def generate_video(prompt, emit_event=None):
    """
    Generate a video using Kie.ai's Veo 3.1 model.

    Same async pattern as images, but:
    - Polls every 20 seconds (video takes longer)
    - Timeout is 300 seconds (5 minutes)
    - Students see the DIFFERENCE between image and video polling

    Args:
        prompt: Video description prompt
        emit_event: Callback for SSE logging

    Returns:
        dict with: video_url, task_id, duration, cost
    """
    emit = emit_event or (lambda *a, **kw: None)
    headers = _get_headers()

    if not headers:
        emit("video", "progress", "No KIE_API_KEY — returning demo video")
        return {
            "video_url": "https://placehold.co/1080x1920/17181C/C7A35A?text=Demo+Video",
            "task_id": "demo_video_task",
            "duration": 0,
            "cost": 0.0,
            "demo": True
        }

    # -- Step 1: Create the video task --
    emit("video", "progress", "Creating video task on Kie.ai (Veo 3.1)...")

    try:
        create_response = requests.post(
            VIDEO_CREATE_URL,
            headers=headers,
            json={
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "model": "veo3_fast"
            },
            timeout=30
        )
        create_response.raise_for_status()
        create_data = create_response.json()

        task_id = create_data.get("taskId") or create_data.get("task_id")
        if not task_id:
            raise Exception(f"No task_id in response: {create_data}")

        emit("video", "progress", f"Video task created: {task_id}")

    except requests.exceptions.RequestException as e:
        emit("video", "error", f"Failed to create video task: {str(e)}")
        raise

    # -- Step 2: Poll for completion --
    # Video polls every 20 seconds (much slower than images!)
    # Timeout after 300 seconds (5 minutes)
    start_time = time.time()
    poll_interval = 20
    timeout = 300
    attempt = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            emit("video", "error", f"Video generation timed out after {timeout}s")
            raise Exception(f"Video generation timed out after {timeout} seconds")

        attempt += 1
        time.sleep(poll_interval)

        try:
            status_response = requests.get(
                VIDEO_STATUS_URL,
                headers=headers,
                params={"taskId": task_id},
                timeout=15
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            state = status_data.get("state", "unknown")

            # -- Emit polling events (students see the long wait!) --
            emit("video", "polling",
                 f"Polling video... attempt {attempt}, status: {state} ({round(elapsed)}s elapsed)",
                 {"attempt": attempt, "state": state, "elapsed": round(elapsed, 1)})

            if state == "success":
                video_url = status_data.get("url") or status_data.get("video_url", "")
                # Also check nested results
                if not video_url:
                    results = status_data.get("results", {})
                    video_url = results.get("url") or results.get("video_url", "")

                duration = round(time.time() - start_time, 1)
                cost = 0.19  # Approximate cost per video

                emit("video", "progress",
                     f"Complete! Video ready in {duration}s")

                return {
                    "video_url": video_url,
                    "task_id": task_id,
                    "duration": duration,
                    "cost": cost,
                    "demo": False
                }

            elif state in ("failed", "error"):
                error_msg = status_data.get("error", "Unknown error")
                emit("video", "error", f"Video generation failed: {error_msg}")
                raise Exception(f"Video generation failed: {error_msg}")

        except requests.exceptions.RequestException as e:
            emit("video", "progress", f"Poll request failed (attempt {attempt}), retrying...")
