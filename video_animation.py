import replicate
import os
import asyncio

async def animate_image(image_url: str, animation_type: str = "turn"):
    """
    Анимирует фото с помощью Kling v2.1
    
    Args:
        image_url: URL изображения для анимации
        animation_type: тип анимации ("turn", "step", "walk")
    
    Returns:
        URL видео файла
    """
    
    # Промпты для разных типов анимации
    prompts = {
        "turn": "A woman in fashionable clothing elegantly turning around, smooth rotation, studio lighting, professional fashion photography",
        "step": "A woman in fashionable clothing confidently taking a step forward, natural movement, studio environment",
        "walk": "A woman in fashionable clothing walking forward with graceful model walk, smooth movement, professional setting"
    }
    
    prompt = prompts.get(animation_type, prompts["turn"])
    
    print(f"DEBUG: Запуск анимации типа '{animation_type}'")
    print(f"DEBUG: Image URL: {image_url}")
    print(f"DEBUG: Prompt: {prompt}")
    
    try:
        # Используем Kling v2.1 - лучшая модель для анимации людей
        output = await replicate.async_run(
            "kwaivgi/kling-v2.1:2a24bd726cb9e0e58b3bd5e6a7fde0ec3aa2c89e44f91e57f64e85be40e79fb1",
            input={
                "prompt": prompt,
                "image_url": image_url,
                "output_video_type": "mp4",
                "duration": "5",
                "aspect_ratio": "9:16",
                "negative_prompt": "distorted, blurry, low quality, disfigured, ugly, horror"
            }
        )
        
        # Output от Kling v2.1 обычно строка с URL
        if isinstance(output, str):
            video_url = output
        elif isinstance(output, list) and len(output) > 0:
            video_url = str(output[0])
        else:
            raise Exception(f"Unexpected output format: {type(output)}, value: {output}")
        
        print(f"DEBUG: Видео успешно создано: {video_url}")
        return video_url
        
    except Exception as e:
        print(f"DEBUG: Ошибка в Kling v2.1: {e}")
        raise e
