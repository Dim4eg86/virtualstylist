import replicate
import os

async def generate_vton_image(human_url, garment_url, category):
    """
    Генерация виртуальной примерки через CatVTON-Flux
    
    CatVTON лучше работает с платьями чем IDM-VTON!
    
    Args:
        human_url: URL фото человека
        garment_url: URL фото одежды
        category: Категория одежды ("верх", "низ", "платье") - для совместимости, но не используется
    
    Returns:
        str: URL сгенерированного изображения
    """
    # CatVTON-Flux - модель которая хорошо работает с платьями!
    model_name = "mmezhov/catvton-flux"
    
    print(f"DEBUG replicate_api.py (CatVTON): Получена категория='{category}' (не используется, CatVTON определяет сама)")
    
    try:
        print(f"DEBUG replicate_api.py (CatVTON): Запускаем CatVTON-Flux")
        
        output = await replicate.async_run(
            model_name,
            input={
                "image": human_url,          # Фото человека
                "garment_image": garment_url, # Фото одежды
                "num_inference_steps": 30,    # 30 шагов = хорошее качество
                "guidance_scale": 2.5,        # Сила влияния промпта
                "seed": -1,                   # Случайный seed
            }
        )
        
        print(f"DEBUG replicate_api.py (CatVTON): Генерация завершена успешно. Тип output: {type(output)}")
        
        # Обработка результата
        if isinstance(output, list):
            result = str(output[0])
            print(f"DEBUG replicate_api.py (CatVTON): Возвращаем URL из списка: {result[:100]}...")
            return result
        
        result = str(output)
        print(f"DEBUG replicate_api.py (CatVTON): Возвращаем URL: {result[:100]}...")
        return result
        
    except Exception as e:
        print(f"DEBUG replicate_api.py (CatVTON): ОШИБКА при генерации - {e}")
        raise e
