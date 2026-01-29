import replicate
import os
from fashn_api import generate_vton_fashn

async def generate_vton_image(human_url, garment_url, category):
    """
    Генерация виртуальной примерки с выбором модели
    
    - Платья: FASHN v1.5 (FAL.AI) - категория "one-pieces"
    - Верх/Низ: IDM-VTON (Replicate)
    
    Args:
        human_url: URL фото человека
        garment_url: URL фото одежды
        category: Категория одежды ("верх", "низ", "платье")
    
    Returns:
        str: URL сгенерированного изображения
    """
    print(f"DEBUG replicate_api.py: Получена категория='{category}'")
    
    # Для платьев используем FASHN v1.5
    if category.lower() in ["платье", "dress", "dresses"]:
        print(f"DEBUG replicate_api.py: Используем FASHN v1.5 для платья")
        return await generate_vton_fashn(human_url, garment_url, category)
    else:
        print(f"DEBUG replicate_api.py: Используем IDM-VTON для {category}")
        return await generate_vton_idm(human_url, garment_url, category)


async def generate_vton_idm(human_url, garment_url, category):
    """
    IDM-VTON - для верха и низа
    """
    # IDM-VTON - быстрая и надёжная модель
    model_version = "cuuupid/idm-vton:906425dbca90663ff5427624839572cc56ea7d380343d13e2a4c4b09d3f0c30f"
    
    print(f"DEBUG replicate_api.py (IDM): Получена категория='{category}'")
    
    # Маппинг категорий
    category_mapping = {
        "верх": "upper_body",
        "низ": "lower_body",
        "upper_body": "upper_body",
        "lower_body": "lower_body"
    }
    
    model_category = category_mapping.get(category.lower(), "upper_body")
    
    print(f"DEBUG replicate_api.py (IDM): Маппинг '{category}' -> '{model_category}'")
    
    try:
        garment_description = "High quality clothing item"
        steps = 20
        
        print(f"DEBUG replicate_api.py (IDM): Промпт='{garment_description}', steps={steps}")
        
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
                "crop": True,
                "denoise_steps": steps,
                "guidance_scale": 2.0
            }
        )
        
        print(f"DEBUG replicate_api.py (IDM): Генерация завершена успешно")
        
        if isinstance(output, list):
            return str(output[0])
        
        return str(output)
        
    except Exception as e:
        print(f"DEBUG replicate_api.py (IDM): ОШИБКА - {e}")
        raise e
