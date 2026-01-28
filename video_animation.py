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
        "turn": "A woman in fashionable clothing elegantly turning around, smooth rotation, studio lighting, professional fashion photography",
        "step": "A woman in fashionable clothing confidently taking a step forward, natural movement, studio environment",
        "walk": "A woman in fashionable clothing walking forward with graceful model walk, smooth movement, professional setting"
    }
    
    prompt = prompts.get(animation_type, prompts["turn"])
    
    print(f"DEBUG: Запуск анимации типа '{animation_type}'")
    print(f"DEBUG: Image URL: {image_url}")
    print(f"DEBUG: Prompt: {prompt}")
    
    try:
        # Используем актуальную официальную модель Kling v2.1
        # Это image-to-video модель, официально доступная на Replicate
        output = await replicate.async_run(
            "kling-ai/kling-v2.1-image-to-video",
            input={
                "prompt": prompt,
                "start_image": image_url,  # Параметр для входного изображения
                "duration": "5",            # 5 секунд видео
                "aspect_ratio": "9:16",     # Вертикальное видео
                "cfg_scale": 0.5,           # Classifier-free guidance
                "negative_prompt": "distorted, blurry, low quality, disfigured, ugly, horror, warped face, bad anatomy"
            }
        )
        
        print(f"DEBUG: Output type: {type(output)}")
        print(f"DEBUG: Output value: {output}")
        
        # Output от Kling обычно строка с URL или FileOutput объект
        if isinstance(output, str):
            video_url = output
        elif isinstance(output, list) and len(output) > 0:
            video_url = str(output[0])
        elif hasattr(output, 'url'):
            video_url = output.url
        else:
            raise Exception(f"Unexpected output format: {type(output)}, value: {output}")
        
        print(f"DEBUG: Видео успешно создано: {video_url}")
        return video_url
        
    except replicate.exceptions.ReplicateError as e:
        print(f"DEBUG: Ошибка Replicate API: {e}")
        print(f"DEBUG: Попытка использовать альтернативную модель...")
        
        # Альтернатива: попробуем Kling v2.5 Turbo
        try:
            output = await replicate.async_run(
                "kling-ai/kling-v2.5",
                input={
                    "prompt": prompt,
                    "image": image_url,
                    "duration": 5,
                    "aspect_ratio": "9:16",
                    "negative_prompt": "distorted, blurry, low quality"
                }
            )
            
            if isinstance(output, str):
                video_url = output
            elif isinstance(output, list):
                video_url = str(output[0])
            else:
                video_url = str(output)
            
            print(f"DEBUG: Видео создано через альтернативную модель: {video_url}")
            return video_url
            
        except Exception as e2:
            print(f"DEBUG: Альтернативная модель тоже не сработала: {e2}")
            raise e
        
    except Exception as e:
        print(f"DEBUG: Общая ошибка при создании видео: {e}")
        raise e
