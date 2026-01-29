import replicate
import os

async def generate_vton_image(human_url, garment_url, category):
    """
    Генерация виртуальной примерки через IDM-VTON
    
    Оптимизировано для работы с платьями
    
    Args:
        human_url: URL фото человека
        garment_url: URL фото одежды
        category: Категория одежды ("верх", "низ", "платье")
    
    Returns:
        str: URL сгенерированного изображения
    """
    # IDM-VTON - быстрая и доступная модель
    model_version = "cuuupid/idm-vton:906425dbca90663ff5427624839572cc56ea7d380343d13e2a4c4b09d3f0c30f"
    
    print(f"DEBUG replicate_api.py: Получена категория='{category}'")
    
    # Для платьев используем upper_body (работает лучше чем dresses)
    category_mapping = {
        "верх": "upper_body",
        "низ": "lower_body",
        "платье": "upper_body",  # Платья как верх
        "upper_body": "upper_body",
        "lower_body": "lower_body",
        "dresses": "upper_body"
    }
    
    model_category = category_mapping.get(category.lower(), "upper_body")
    
    print(f"DEBUG replicate_api.py: Маппинг '{category}' -> '{model_category}'")
    
    try:
        # Для платьев - очень детальный промпт
        if category.lower() in ["платье", "dress", "dresses"]:
            garment_description = "A complete full-length elegant dress garment, one-piece clothing item from top to bottom, long dress"
            steps = 30  # Больше шагов для лучшего качества
        else:
            garment_description = "High quality clothing item"
            steps = 20  # Быстрее для верха и низа
        
        print(f"DEBUG replicate_api.py: Промпт='{garment_description}', steps={steps}")
        
        output = await replicate.async_run(
            model_version,
            input={
                "human_img": human_url,
                "garm_img": garment_url,
                "garment_des": garment_description,
                "category": model_category,
                "n_samples": 1,
                "n_steps": steps,
                "seed": -1,
                "crop": True,               # Правильные пропорции 3:4
                "denoise_steps": steps,
                "guidance_scale": 2.0
            }
        )
        
        print(f"DEBUG replicate_api.py: Генерация завершена успешно")
        
        if isinstance(output, list):
            result = str(output[0])
            return result
        
        return str(output)
        
    except Exception as e:
        print(f"DEBUG replicate_api.py: ОШИБКА - {e}")
        raise e
