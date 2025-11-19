# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name

import asyncio
import os
import time

import pytest
from agentscope_runtime.common.skills.generations import (
    ImageEdit,
    ImageEditInput,
)
from agentscope_runtime.common.skills.generations import (
    ImageEditWan25,
    ImageEditWan25Input,
)
from agentscope_runtime.common.skills.generations import (
    ImageGeneration,
    ImageGenInput,
)
from agentscope_runtime.common.skills.generations import (
    ImageGenerationWan25,
    ImageGenerationWan25Input,
)
from agentscope_runtime.common.skills.generations import (
    ImageStyleRepaint,
    ImageStyleRepaintInput,
)
from agentscope_runtime.common.skills.generations import (
    ImageToVideo,
    ImageToVideoInput,
)
from agentscope_runtime.common.skills.generations import (
    ImageToVideoSubmit,
    ImageToVideoSubmitInput,
    ImageToVideoFetch,
    ImageToVideoFetchInput,
)
from agentscope_runtime.common.skills.generations import (
    ImageToVideoWan25Submit,
    ImageToVideoWan25SubmitInput,
    ImageToVideoWan25Fetch,
    ImageToVideoWan25FetchInput,
)
from agentscope_runtime.common.skills.generations import (
    QwenImageEdit,
    QwenImageEditInput,
)
from agentscope_runtime.common.skills.generations import (
    QwenImageGen,
    QwenImageGenInput,
)
from agentscope_runtime.common.skills.generations import (
    QwenTextToSpeech,
    QwenTextToSpeechInput,
)
from agentscope_runtime.common.skills.generations import (
    SpeechToText,
    SpeechToTextInput,
)
from agentscope_runtime.common.skills.generations import (
    SpeechToVideo,
    SpeechToVideoInput,
)
from agentscope_runtime.common.skills.generations import (
    SpeechToVideoSubmit,
    SpeechToVideoSubmitInput,
    SpeechToVideoFetch,
    SpeechToVideoFetchInput,
)
from agentscope_runtime.common.skills.generations import (
    TextToVideoSubmit,
    TextToVideoSubmitInput,
    TextToVideoFetch,
    TextToVideoFetchInput,
)
from agentscope_runtime.common.skills.generations import (
    TextToVideoWan25Submit,
    TextToVideoWan25SubmitInput,
    TextToVideoWan25Fetch,
    TextToVideoWan25FetchInput,
)

# ============================================================================
# Image to Video Tests (Async API - Submit/Fetch Pattern)
# ============================================================================

NO_LONGRUN_TEST = os.getenv("NO_LONGRUN_TEST", "true") == "true"


@pytest.fixture
def image_to_video_submit():
    return ImageToVideoSubmit()


@pytest.fixture
def image_to_video_fetch():
    return ImageToVideoFetch()


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_LONGRUN_TEST,
    reason="take more than 5 mins, skip for " "saving time",
)
async def test_async_image_to_video(
    image_to_video_submit,
    image_to_video_fetch,
):
    """Test async image to video generation with submit/fetch pattern"""
    image_url = (
        "https://dashscope.oss-cn-beijing.aliyuncs.com"
        "/images/dog_and_girl.jpeg"
    )

    test_inputs = [
        ImageToVideoSubmitInput(
            image_url=image_url,
            prompt="女孩把小狗抱起来",
            resolution="1080P",
            prompt_extend=True,
        ),
    ]

    start_time = time.time()

    try:
        # Step 1: Submit async tasks concurrently
        submit_tasks = [
            image_to_video_submit.arun(test_input)
            for test_input in test_inputs
        ]

        submit_results = await asyncio.gather(
            *submit_tasks,
            return_exceptions=True,
        )

        # Step 2: Extract task_ids from successful submissions
        task_ids = []
        for result in submit_results:
            if not isinstance(result, Exception):
                task_ids.append(result.task_id)
                assert result.task_id
                assert result.task_status in [
                    "PENDING",
                    "RUNNING",
                    "SUCCEEDED",
                ]

        assert len(task_ids) > 0

        # Step 3: Poll for task completion using ImageToVideoFetch
        max_wait_time = 600  # 10 minutes timeout
        poll_interval = 5  # 5 seconds polling interval
        completed_tasks = {}

        poll_start_time = time.time()

        while len(completed_tasks) < len(task_ids):
            await asyncio.sleep(poll_interval)

            remaining_task_ids = [
                task_id
                for task_id in task_ids
                if task_id not in completed_tasks
            ]

            if not remaining_task_ids:
                break

            fetch_tasks = [
                image_to_video_fetch.arun(
                    ImageToVideoFetchInput(task_id=task_id),
                )
                for task_id in remaining_task_ids
            ]

            fetch_results = await asyncio.gather(
                *fetch_tasks,
                return_exceptions=True,
            )

            # Process fetch results
            for task_id, fetch_result in zip(
                remaining_task_ids,
                fetch_results,
            ):
                if isinstance(fetch_result, Exception):
                    continue

                status = fetch_result.task_status
                if status == "SUCCEEDED":
                    completed_tasks[task_id] = fetch_result
                    assert fetch_result.video_url
                    assert fetch_result.request_id
                elif status in ["FAILED", "CANCELED"]:
                    completed_tasks[task_id] = fetch_result

            # Check timeout
            if time.time() - poll_start_time > max_wait_time:
                break

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0
        # Verify at least some tasks completed
        assert len(completed_tasks) > 0

    except Exception as e:
        pytest.fail(f"Unexpected error during execution: {str(e)}")


# ============================================================================
# Speech to Video Tests (Async API - Submit/Fetch Pattern)
# ============================================================================


@pytest.fixture
def speech_to_video_submit():
    return SpeechToVideoSubmit()


@pytest.fixture
def speech_to_video_fetch():
    return SpeechToVideoFetch()


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_LONGRUN_TEST,
    reason="take more than 5 mins, skip for saving time",
)
async def test_async_speech_to_video(
    speech_to_video_submit,
    speech_to_video_fetch,
):
    """Test async speech to video generation with submit/fetch pattern"""
    image_url = (
        "https://img.alicdn.com/imgextra/i3/O1CN011FObkp1T7Ttow"
        "oq4F_!!6000000002335-0-tps-1440-1797.jpg"
    )

    audio_url = (
        "https://help-static-aliyun-doc.aliyuncs.com/"
        "file-manage-files/zh-CN/20250825/iaqpio/input_audio.MP3"
    )

    test_inputs = [
        SpeechToVideoSubmitInput(
            image_url=image_url,
            audio_url=audio_url,
            resolution="480P",
        ),
    ]

    start_time = time.time()

    try:
        # Step 1: Submit async tasks
        submit_tasks = [
            speech_to_video_submit.arun(
                test_input,
                model_name="wan2.2-s2v",
            )
            for test_input in test_inputs
        ]

        submit_results = await asyncio.gather(
            *submit_tasks,
            return_exceptions=True,
        )

        # Step 2: Extract task_ids
        task_ids = []
        for result in submit_results:
            if not isinstance(result, Exception):
                task_ids.append(result.task_id)
                assert result.task_id
                assert result.task_status

        assert len(task_ids) > 0

        # Step 3: Poll for completion
        max_wait_time = 600
        poll_interval = 5
        completed_tasks = {}

        poll_start_time = time.time()

        while len(completed_tasks) < len(task_ids):
            await asyncio.sleep(poll_interval)

            remaining_task_ids = [
                task_id
                for task_id in task_ids
                if task_id not in completed_tasks
            ]

            if not remaining_task_ids:
                break

            fetch_tasks = [
                speech_to_video_fetch.arun(
                    SpeechToVideoFetchInput(task_id=task_id),
                )
                for task_id in remaining_task_ids
            ]

            fetch_results = await asyncio.gather(
                *fetch_tasks,
                return_exceptions=True,
            )

            for task_id, fetch_result in zip(
                remaining_task_ids,
                fetch_results,
            ):
                if isinstance(fetch_result, Exception):
                    continue

                status = fetch_result.task_status
                if status == "SUCCEEDED":
                    completed_tasks[task_id] = fetch_result
                    if fetch_result.video_url:
                        assert fetch_result.video_url
                elif status in ["FAILED", "CANCELED"]:
                    completed_tasks[task_id] = fetch_result

            if time.time() - poll_start_time > max_wait_time:
                break

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        assert len(completed_tasks) > 0

    except Exception as e:
        pytest.fail(f"Unexpected error during execution: {str(e)}")


# ============================================================================
# Text to Video Tests (Async API - Submit/Fetch Pattern)
# ============================================================================


@pytest.fixture
def text_to_video_submit():
    return TextToVideoSubmit()


@pytest.fixture
def text_to_video_fetch():
    return TextToVideoFetch()


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_LONGRUN_TEST,
    reason="take more than 5 mins, skip for saving time",
)
async def test_async_text_to_video(
    text_to_video_submit,
    text_to_video_fetch,
):
    """Test async text to video generation with submit/fetch pattern"""
    test_inputs = [
        TextToVideoSubmitInput(
            prompt="A cute panda playing in a bamboo forest, "
            "peaceful nature scene",
            negative_prompt="dark, scary, violent",
            prompt_extend=True,
        ),
    ]

    start_time = time.time()

    try:
        # Step 1: Submit async tasks
        submit_tasks = [
            text_to_video_submit.arun(
                test_input,
                model_name="wan2.2-t2v-plus",
            )
            for test_input in test_inputs
        ]

        submit_results = await asyncio.gather(
            *submit_tasks,
            return_exceptions=True,
        )

        # Step 2: Extract task_ids
        task_ids = []
        for result in submit_results:
            if not isinstance(result, Exception):
                task_ids.append(result.task_id)
                assert result.task_id
                assert result.task_status

        assert len(task_ids) > 0

        # Step 3: Poll for completion
        max_wait_time = 600
        poll_interval = 5
        completed_tasks = {}

        poll_start_time = time.time()

        while len(completed_tasks) < len(task_ids):
            await asyncio.sleep(poll_interval)

            remaining_task_ids = [
                task_id
                for task_id in task_ids
                if task_id not in completed_tasks
            ]

            if not remaining_task_ids:
                break

            fetch_tasks = [
                text_to_video_fetch.arun(
                    TextToVideoFetchInput(task_id=task_id),
                )
                for task_id in remaining_task_ids
            ]

            fetch_results = await asyncio.gather(
                *fetch_tasks,
                return_exceptions=True,
            )

            for task_id, fetch_result in zip(
                remaining_task_ids,
                fetch_results,
            ):
                if isinstance(fetch_result, Exception):
                    continue

                status = fetch_result.task_status
                if status == "SUCCEEDED":
                    completed_tasks[task_id] = fetch_result
                    assert fetch_result.video_url
                elif status in ["FAILED", "CANCELED"]:
                    completed_tasks[task_id] = fetch_result

            if time.time() - poll_start_time > max_wait_time:
                break

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        assert len(completed_tasks) > 0

    except Exception as e:
        pytest.fail(f"Unexpected error during execution: {str(e)}")


# ============================================================================
# Image Edit Tests
# ============================================================================


@pytest.fixture
def image_edit():
    return ImageEdit()


@pytest.mark.asyncio
async def test_image_edit(image_edit):
    """Test image editing functionality"""
    image_edit_input = ImageEditInput(
        function="remove_watermark",
        base_image_url="https://mcdn.watermarkremover.ai/web-cdn"
        "/watermarkremover/production/anon-398e601a-53ca-4b50"
        "-959d-bc359ff85d31/img/1750251591975"
        "-b6b7cc6af66b4119371705687fc520b1.jpg",
        prompt="去除图像中的水印",
        n=2,
    )

    result = await image_edit.arun(image_edit_input)

    assert result.results
    assert isinstance(result.results, list)
    assert len(result.results) > 0
    assert result.request_id


# ============================================================================
# Image Generation Tests
# ============================================================================


@pytest.fixture
def image_generation():
    return ImageGeneration()


@pytest.mark.asyncio
async def test_image_generation(image_generation):
    """Test image generation from text"""
    image_gen_input = ImageGenInput(
        prompt="帮我画一个国宝熊猫,",
    )

    result = await image_generation.arun(
        image_gen_input,
        model_name="qwen-image",
    )

    assert result.results
    assert isinstance(result.results, list)
    assert len(result.results) > 0
    assert result.request_id


# ============================================================================
# Image Style Repaint Tests
# ============================================================================


@pytest.fixture
def image_style_repaint():
    return ImageStyleRepaint()


@pytest.mark.asyncio
async def test_image_style_repaint(image_style_repaint):
    """Test image style repainting"""
    image_style_repaint_input = ImageStyleRepaintInput(
        image_url="https://public-vigen-video.oss-cn-shanghai.aliyuncs.com"
        "/public/dashscope/test.png",
        style_index=5,
    )

    result = await image_style_repaint.arun(
        image_style_repaint_input,
    )

    assert result.results
    assert isinstance(result.results, list)
    assert len(result.results) > 0
    assert result.request_id


# ============================================================================
# Image to Video Tests (Sync API - with polling)
# ============================================================================


@pytest.fixture
def image_to_video():
    return ImageToVideo()


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_LONGRUN_TEST,
    reason="take more than 5 mins, skip for saving time",
)
async def test_image_to_video(image_to_video):
    """Test image to video generation with concurrent execution"""
    image_url = (
        "https://dashscope.oss-cn-beijing.aliyuncs.com"
        "/images/dog_and_girl.jpeg"
    )

    test_inputs = [
        ImageToVideoInput(
            image_url=image_url,
            prompt="女孩把小狗抱起来",
            resolution="1080P",
            prompt_extend=True,
        ),
        ImageToVideoInput(
            image_url=image_url,
            prompt="小狗把女孩抱起来",
            resolution="480P",
            prompt_extend=True,
        ),
    ]

    start_time = time.time()

    try:
        # Execute concurrent calls using asyncio.gather
        tasks = [image_to_video.arun(test_input) for test_input in test_inputs]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify results
        successful_results = [
            r for r in results if not isinstance(r, Exception)
        ]

        assert len(successful_results) > 0

        for result in successful_results:
            assert result.video_url
            assert result.request_id

    except Exception as e:
        pytest.fail(f"Unexpected error during concurrent execution: {str(e)}")


# ============================================================================
# Qwen Image Edit Tests
# ============================================================================


@pytest.fixture
def qwen_image_edit():
    return QwenImageEdit()


@pytest.mark.asyncio
async def test_qwen_image_edit(qwen_image_edit):
    """Test Qwen image editing"""
    base_image_url = (
        "https://dashscope.oss-cn-beijing.aliyuncs.com/images"
        "/dog_and_girl.jpeg"
    )

    test_inputs = [
        QwenImageEditInput(
            image_url=base_image_url,
            prompt="将图中的人物改为站立姿势，弯腰握住狗的前爪",
            negative_prompt="",
        ),
    ]

    start_time = time.time()

    try:
        tasks = [
            qwen_image_edit.arun(test_input) for test_input in test_inputs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify results
        successful_results = [
            r for r in results if not isinstance(r, Exception)
        ]

        assert len(successful_results) > 0

        for result in successful_results:
            assert result.results
            assert isinstance(result.results, list)
            assert result.request_id

    except Exception as e:
        pytest.fail(f"Unexpected error during concurrent execution: {str(e)}")


# ============================================================================
# Qwen Image Generation Tests
# ============================================================================


@pytest.fixture
def qwen_image_gen():
    return QwenImageGen()


@pytest.mark.asyncio
async def test_qwen_image_gen(qwen_image_gen):
    """Test Qwen image generation"""
    test_inputs = [
        QwenImageGenInput(
            prompt="沙滩上小男孩和一只金毛并排坐着",
            negative_prompt="",
        ),
        QwenImageGenInput(
            prompt="沙滩上小女孩和一只柯基并排坐着",
        ),
    ]

    start_time = time.time()

    try:
        tasks = [qwen_image_gen.arun(test_input) for test_input in test_inputs]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify results
        successful_results = [
            r for r in results if not isinstance(r, Exception)
        ]

        assert len(successful_results) > 0

        for result in successful_results:
            assert result.results
            assert isinstance(result.results, list)
            assert result.request_id

    except Exception as e:
        pytest.fail(f"Unexpected error during concurrent execution: {str(e)}")


# ============================================================================
# Qwen Text to Speech Tests
# ============================================================================


@pytest.fixture
def qwen_text_to_speech():
    return QwenTextToSpeech()


@pytest.mark.asyncio
async def test_qwen_text_to_speech(qwen_text_to_speech):
    """Test Qwen text to speech"""
    test_inputs = [
        QwenTextToSpeechInput(
            text="沙滩上小男孩和一只金毛并排坐着",
        ),
        QwenTextToSpeechInput(
            text="沙滩上小女孩和一只柯基并排坐着",
        ),
    ]

    start_time = time.time()

    try:
        tasks = [
            qwen_text_to_speech.arun(test_input) for test_input in test_inputs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify results
        successful_results = [
            r for r in results if not isinstance(r, Exception)
        ]

        assert len(successful_results) > 0

        for result in successful_results:
            assert result.result
            assert result.request_id

    except Exception as e:
        pytest.fail(f"Unexpected error during concurrent execution: {str(e)}")


# ============================================================================
# WAN25 Skills Tests
# ============================================================================


@pytest.fixture
def image_edit_wan25():
    return ImageEditWan25()


@pytest.mark.asyncio
@pytest.mark.skipif(NO_LONGRUN_TEST, reason="requires DASHSCOPE_API_KEY")
async def test_image_edit_wan25(image_edit_wan25):
    """Test WAN25 image editing functionality"""
    images = [
        "https://img.alicdn.com/imgextra/i4/O1CN01TlDlJe1LR9zso3xAC_"
        "!!6000000001295-2-tps-1104-1472.png",
        "https://img.alicdn.com/imgextra/i4/O1CN01M9azZ41YdblclkU6Z_"
        "!!6000000003082-2-tps-1696-960.png",
    ]

    image_edit_input = ImageEditWan25Input(
        images=images,
        prompt="将图1中的闹钟放置到图2的餐桌的花瓶旁边位置",
        n=1,
    )

    result = await image_edit_wan25.arun(image_edit_input)

    assert result.results
    assert isinstance(result.results, list)
    assert len(result.results) > 0
    assert result.request_id
    assert image_edit_wan25.function_schema.model_dump()


@pytest.fixture
def image_generation_wan25():
    return ImageGenerationWan25()


@pytest.mark.asyncio
@pytest.mark.skipif(NO_LONGRUN_TEST, reason="requires DASHSCOPE_API_KEY")
async def test_image_generation_wan25(image_generation_wan25):
    """Test WAN25 image generation functionality"""
    image_gen_input = ImageGenerationWan25Input(
        prompt="帮我画一个国宝熊猫,",
    )

    result = await image_generation_wan25.arun(image_gen_input)

    assert result.results
    assert isinstance(result.results, list)
    assert len(result.results) > 0
    assert result.request_id
    assert image_generation_wan25.function_schema.model_dump()


@pytest.fixture
def image_to_video_wan25_submit():
    return ImageToVideoWan25Submit()


@pytest.fixture
def image_to_video_wan25_fetch():
    return ImageToVideoWan25Fetch()


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_LONGRUN_TEST,
    reason="take more than 5 mins, skip for saving time and requires API key",
)
async def test_async_image_to_video_wan25(
    image_to_video_wan25_submit,
    image_to_video_wan25_fetch,
):
    """Test async WAN25 image to video generation"""
    audio_url = (
        "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files"
        "/zh-CN/20250923/hbiayh/%E4%BB%8E%E5%86%9B%E8%A1%8C.mp3"
    )

    image_url = (
        "https://dashscope.oss-cn-beijing.aliyuncs.com"
        "/images/dog_and_girl.jpeg"
    )

    test_inputs = [
        ImageToVideoWan25SubmitInput(
            image_url=image_url,
            prompt="女孩把小狗抱起来",
            audio_url=audio_url,
            watermark=True,
        ),
    ]

    start_time = time.time()

    try:
        # Step 1: Submit async tasks concurrently
        submit_tasks = [
            image_to_video_wan25_submit.arun(test_input)
            for test_input in test_inputs
        ]

        submit_results = await asyncio.gather(
            *submit_tasks,
            return_exceptions=True,
        )

        # Step 2: Extract task_ids from successful submissions
        task_ids = []
        for result in submit_results:
            if not isinstance(result, Exception):
                task_ids.append(result.task_id)
                assert result.task_id
                assert result.task_status

        assert len(task_ids) > 0

        # Step 3: Poll for task completion using ImageToVideoWan25Fetch
        max_wait_time = 600  # 10 minutes timeout
        poll_interval = 5  # 5 seconds polling interval
        completed_tasks = {}

        poll_start_time = time.time()

        while len(completed_tasks) < len(task_ids):
            await asyncio.sleep(poll_interval)

            remaining_task_ids = [
                task_id
                for task_id in task_ids
                if task_id not in completed_tasks
            ]

            if not remaining_task_ids:
                break

            fetch_tasks = [
                image_to_video_wan25_fetch.arun(
                    ImageToVideoWan25FetchInput(task_id=task_id),
                )
                for task_id in remaining_task_ids
            ]

            fetch_results = await asyncio.gather(
                *fetch_tasks,
                return_exceptions=True,
            )

            for task_id, fetch_result in zip(
                remaining_task_ids,
                fetch_results,
            ):
                if isinstance(fetch_result, Exception):
                    continue

                status = fetch_result.task_status
                if status == "SUCCEEDED":
                    completed_tasks[task_id] = fetch_result
                    assert fetch_result.video_url
                    assert fetch_result.request_id
                elif status in ["FAILED", "CANCELED"]:
                    completed_tasks[task_id] = fetch_result

            if time.time() - poll_start_time > max_wait_time:
                break

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify at least some tasks completed
        assert len(completed_tasks) > 0

    except Exception as e:
        pytest.fail(f"Unexpected error during execution: {str(e)}")


@pytest.fixture
def text_to_video_wan25_submit():
    return TextToVideoWan25Submit()


@pytest.fixture
def text_to_video_wan25_fetch():
    return TextToVideoWan25Fetch()


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_LONGRUN_TEST,
    reason="take more than 5 mins, skip for saving time and requires API key",
)
async def test_async_text_to_video_wan25(
    text_to_video_wan25_submit,
    text_to_video_wan25_fetch,
):
    """Test async WAN25 text to video generation"""
    audio_url = (
        "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files"
        "/zh-CN/20250923/hbiayh/%E4%BB%8E%E5%86%9B%E8%A1%8C.mp3"
    )

    test_inputs = [
        TextToVideoWan25SubmitInput(
            prompt="A cute panda playing in a bamboo forest, "
            "peaceful nature scene",
            audio_url=audio_url,
        ),
    ]

    start_time = time.time()

    try:
        # Step 1: Submit async tasks concurrently
        submit_tasks = [
            text_to_video_wan25_submit.arun(
                test_input,
                model_name="wan2.5-t2v-preview",
            )
            for test_input in test_inputs
        ]

        submit_results = await asyncio.gather(
            *submit_tasks,
            return_exceptions=True,
        )

        # Step 2: Extract task_ids from successful submissions
        task_ids = []
        for result in submit_results:
            if not isinstance(result, Exception):
                task_ids.append(result.task_id)
                assert result.task_id
                assert result.task_status

        assert len(task_ids) > 0

        # Step 3: Poll for task completion using TextToVideoWan25Fetch
        max_wait_time = 600  # 10 minutes timeout
        poll_interval = 5  # 5 seconds polling interval
        completed_tasks = {}

        poll_start_time = time.time()

        while len(completed_tasks) < len(task_ids):
            await asyncio.sleep(poll_interval)

            remaining_task_ids = [
                task_id
                for task_id in task_ids
                if task_id not in completed_tasks
            ]

            if not remaining_task_ids:
                break

            fetch_tasks = [
                text_to_video_wan25_fetch.arun(
                    TextToVideoWan25FetchInput(task_id=task_id),
                )
                for task_id in remaining_task_ids
            ]

            fetch_results = await asyncio.gather(
                *fetch_tasks,
                return_exceptions=True,
            )

            for task_id, fetch_result in zip(
                remaining_task_ids,
                fetch_results,
            ):
                if isinstance(fetch_result, Exception):
                    continue

                status = fetch_result.task_status
                if status == "SUCCEEDED":
                    completed_tasks[task_id] = fetch_result
                    assert fetch_result.video_url
                elif status in ["FAILED", "CANCELED"]:
                    completed_tasks[task_id] = fetch_result

            if time.time() - poll_start_time > max_wait_time:
                break

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify at least some tasks completed
        assert len(completed_tasks) > 0

    except Exception as e:
        pytest.fail(f"Unexpected error during execution: {str(e)}")


# ============================================================================
# Speech to Text Tests
# ============================================================================


@pytest.fixture
def speech_to_text():
    return SpeechToText()


@pytest.mark.asyncio
async def test_speech_to_text(speech_to_text):
    """Test speech to text transcription"""
    file_urls = [
        "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio"
        "/paraformer/hello_world_female2.wav",
        "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio"
        "/paraformer/hello_world_male2.wav",
    ]

    test_inputs = [
        SpeechToTextInput(
            file_urls=file_urls,
            language_hints=["zh"],
        ),
        SpeechToTextInput(
            file_urls=file_urls,
            language_hints=["zh"],
        ),
    ]

    start_time = time.time()

    try:
        tasks = [
            speech_to_text.arun(test_input, model_name="paraformer-v2")
            for test_input in test_inputs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify results
        successful_results = [
            r for r in results if not isinstance(r, Exception)
        ]

        assert len(successful_results) > 0

        for result in successful_results:
            assert isinstance(result.results, list)
            assert result.request_id

    except Exception as e:
        pytest.fail(f"Unexpected error during concurrent execution: {str(e)}")


# ============================================================================
# Speech to Video Tests (Sync API - with polling)
# ============================================================================


@pytest.fixture
def speech_to_video():
    return SpeechToVideo()


@pytest.mark.asyncio
@pytest.mark.skipif(
    NO_LONGRUN_TEST,
    reason="take more than 5 mins, skip for " "saving time",
)
async def test_speech_to_video(speech_to_video):
    """Test speech to video generation with concurrent execution"""
    image_url = (
        "https://img.alicdn.com/imgextra/i3/O1CN011FObkp1T7Ttow"
        "oq4F_!!6000000002335-0-tps-1440-1797.jpg"
    )

    audio_url = (
        "https://help-static-aliyun-doc.aliyuncs.com/"
        "file-manage-files/zh-CN/20250825/iaqpio/input_audio.MP3"
    )

    test_inputs = [
        SpeechToVideoInput(
            image_url=image_url,
            audio_url=audio_url,
            resolution="480P",
        ),
        SpeechToVideoInput(
            image_url=image_url,
            audio_url=audio_url,
            resolution="720P",
        ),
    ]

    start_time = time.time()

    try:
        # Execute concurrent calls using asyncio.gather
        tasks = [
            speech_to_video.arun(test_input, model_name="wan2.2-s2v")
            for test_input in test_inputs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time
        assert total_time > 0

        # Verify results
        successful_results = [
            r for r in results if not isinstance(r, Exception)
        ]

        assert len(successful_results) > 0

        for result in successful_results:
            assert result.video_url
            assert result.request_id

    except Exception as e:
        pytest.fail(f"Unexpected error during concurrent execution: {str(e)}")
