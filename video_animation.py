import replicate
import os
import asyncio

async def animate_image(image_url: str, animation_type: str = "turn"):
    """
    Анимирует фото с помощью Stable Video Diffusion
    
    Args:
        image_url: URL изображения для анимации
        animation_type: тип анимации ("turn", "step", "walk")
    
    Returns:
        URL видео файла
    """
    
    # Промпты для разных типов анимации
    prompts = {
        "turn": "Woman elegantly turning around, smooth rotation, fashion model style",
        "step": "Woman taking a step forward towards camera, confident movement",
        "walk": "Woman walking forward with runway walk, graceful movement"
    }
    
    prompt = prompts.get(animation_type, prompts["turn"])
    
    print(f"DEBUG: Запуск анимации типа '{animation_type}'")
    print(f"DEBUG: Image URL: {image_url}")
    
    try:
        # Используем Stable Video Diffusion - это бесплатная модель!
        output = await replicate.async_run(
            "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
            input={
                "input_image": image_url,
                "sizing_strategy": "maintain_aspect_ratio",
                "frames_per_second": 6,
                "motion_bucket_id": 127,  # Больше движения
                "cond_aug": 0.02
            }
        )
        
        # Output может быть строкой или списком
        if isinstance(output, list) and len(output) > 0:
            video_url = str(output[0])
        elif isinstance(output, str):
            video_url = output
        else:
            raise Exception(f"Unexpected output format: {type(output)}")
        
        print(f"DEBUG: Видео успешно создано: {video_url}")
        return video_url
        
    except Exception as e:
        print(f"DEBUG: Ошибка в Stable Video Diffusion: {e}")
        raise e
