import replicate
import os
import asyncio

async def animate_image(image_url: str, animation_type: str = "turn"):
    """
    Анимирует фото с помощью проверенных image-to-video моделей
    
    Args:
        image_url: URL изображения для анимации
        animation_type: тип анимации ("turn", "step", "walk")
    
    Returns:
        URL видео файла
    """
    
    # Промпты для разных типов анимации
    prompts = {
        "turn": "woman in fashionable clothing gracefully turning 360 degrees around herself, full rotation, smooth camera movement, professional fashion show style",
        "step": "woman in fashionable clothing confidently stepping forward, natural movement",
        "walk": "woman in fashionable clothing walking with graceful model walk, smooth movement"
    }
    
    prompt = prompts.get(animation_type, prompts["turn"])
    
    print(f"DEBUG: Запуск анимации типа '{animation_type}'")
    print(f"DEBUG: Image URL: {image_url}")
    print(f"DEBUG: Prompt: {prompt}")
    
    try:
        # ВАРИАНТ 1: Hailuo 2 - быстрая и качественная модель (РЕКОМЕНДУЕТСЯ)
        print(f"DEBUG: Пробуем Hailuo 2...")
        output = await replicate.async_run(
            "minimax/hailuo-02",
            input={
                "prompt": prompt,
                "image": image_url,
                "duration": 10,  # 10 секунд (число, не строка!)
            }
        )
        
        print(f"DEBUG: Output type: {type(output)}")
        
        # Обработка результата
        if isinstance(output, str):
            video_url = output
        elif isinstance(output, list) and len(output) > 0:
            video_url = str(output[0])
        elif hasattr(output, 'url'):
            video_url = output.url
        else:
            video_url = str(output)
        
        print(f"DEBUG: Видео успешно создано через Hailuo 2: {video_url}")
        return video_url
        
    except Exception as e:
        print(f"DEBUG: Hailuo 2 не сработал: {e}")
        print(f"DEBUG: Пробуем альтернативу WAN 2.2...")
        
        try:
            # ВАРИАНТ 2: WAN 2.2 Fast - альтернатива
            output = await replicate.async_run(
                "wan-video/wan-2.2-i2v-fast",
                input={
                    "prompt": prompt,
                    "image": image_url,
                }
            )
            
            if isinstance(output, str):
                video_url = output
            elif isinstance(output, list):
                video_url = str(output[0])
            else:
                video_url = str(output)
            
            print(f"DEBUG: Видео создано через WAN 2.2: {video_url}")
            return video_url
            
        except Exception as e2:
            print(f"DEBUG: WAN 2.2 тоже не сработал: {e2}")
            print(f"DEBUG: Пробуем последнюю альтернативу - SVD...")
            
            try:
                # ВАРИАНТ 3: Stable Video Diffusion - последняя попытка
                output = await replicate.async_run(
                    "stability-ai/stable-video-diffusion",
                    input={
                        "input_image": image_url,
                        "cond_aug": 0.02,
                        "decoding_t": 7,
                        "video_length": "14_frames_with_svd",
                        "sizing_strategy": "maintain_aspect_ratio",
                        "motion_bucket_id": 127,
                        "frames_per_second": 6
                    }
                )
                
                if isinstance(output, str):
                    video_url = output
                elif isinstance(output, list):
                    video_url = str(output[0])
                else:
                    video_url = str(output)
                
                print(f"DEBUG: Видео создано через Stable Video Diffusion: {video_url}")
                return video_url
                
            except Exception as e3:
                print(f"DEBUG: Все модели не сработали!")
                print(f"DEBUG: Hailuo 2: {e}")
                print(f"DEBUG: WAN 2.2: {e2}")
                print(f"DEBUG: SVD: {e3}")
                raise Exception("Все video модели недоступны. Попробуйте позже.")

