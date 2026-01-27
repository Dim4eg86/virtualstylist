import replicate
import os
import asyncio

async def animate_image(image_url: str, animation_type: str = "turn"):
    """
    Анимирует фото с помощью Kling AI
    
    Args:
        image_url: URL изображения для анимации
        animation_type: тип анимации ("turn", "step", "walk")
    
    Returns:
        URL видео файла
    """
    
    # Промпты для разных типов анимации
    prompts = {
        "turn": "Woman elegantly turning around 180 degrees, smooth rotation, fashion model style, studio lighting",
        "step": "Woman confidently taking a step forward towards camera, slight smile, professional demeanor",
        "walk": "Woman walking forward with model runway walk, graceful movement, confident posture, fashion show style"
    }
    
    prompt = prompts.get(animation_type, prompts["turn"])
    
    print(f"DEBUG: Запуск анимации типа '{animation_type}'")
    print(f"DEBUG: Image URL: {image_url}")
    
    try:
        # Используем Kling AI для генерации видео из изображения
        output = await replicate.async_run(
            "fofr/kling-video:5a0cb2d333033e0830c137f137bc8e5f5c0df3f0903c13f61c167c1bcd48f656",
            input={
                "prompt": prompt,
                "image": image_url,
                "duration": "5",  # 5 секунд
                "aspect_ratio": "9:16"  # Вертикальное видео
            }
        )
        
        if isinstance(output, list) and len(output) > 0:
            video_url = str(output[0])
        elif isinstance(output, str):
            video_url = output
        else:
            raise Exception(f"Unexpected output format: {type(output)}")
        
        print(f"DEBUG: Видео успешно создано: {video_url}")
        return video_url
        
    except Exception as e:
        print(f"DEBUG: Ошибка в Kling AI: {e}")
        raise e
