import replicate
import os

async def generate_vton_image(human_url, garment_url, category):
    """
    Генерация виртуальной примерки через IDM-VTON
    
    Args:
        human_url: URL фото человека
        garment_url: URL фото одежды
        category: Категория одежды ("верх", "низ", "платье")
    
    Returns:
        str: URL сгенерированного изображения
    """
    # IDM-VTON - быстрая модель (20-30 сек вместо 5-7 минут)
    model_version = "cuuupid/idm-vton:906425dbca90663ff5427624839572cc56ea7d380343d13e2a4c4b09d3f0c30f"
    
    print(f"DEBUG replicate_api.py: Получена категория='{category}'")
    
    # Маппинг русских категорий на категории IDM-VTON
    category_mapping = {
        "верх": "upper_body",
        "низ": "lower_body",
        "платье": "dresses",
        # На всякий случай английские варианты
        "upper_body": "upper_body",
        "lower_body": "lower_body",
        "dresses": "dresses"
    }
    
    model_category = category_mapping.get(category.lower(), "upper_body")
    
    print(f"DEBUG replicate_api.py: Маппинг '{category}' -> '{model_category}'")
    
    try:
        # Специальный промпт для платьев чтобы модель не разделяла на части
        if model_category == "dresses":
            garment_description = "A complete one-piece dress garment, full-length clothing item"
        else:
            garment_description = "High quality clothing item"
        
        output = await replicate.async_run(
            model_version,
            input={
                "human_img": human_url,
                "garm_img": garment_url,
                "garment_des": garment_description,
                "category": model_category,
                "n_samples": 1,
                "n_steps": 20,              # 20 = быстро (~20 сек), 30 = лучше качество
                "seed": -1,
                # КРИТИЧЕСКИ ВАЖНО: crop=True для правильных пропорций 3:4
                "crop": True,               # Автокроп под формат 768x1024 (3:4)
                # Дополнительные параметры
                "denoise_steps": 20,
                "guidance_scale": 2.0
            }
        )
        
        print(f"DEBUG replicate_api.py: Генерация IDM-VTON завершена успешно. Тип output: {type(output)}")
        
        if isinstance(output, list):
            result = str(output[0])
            print(f"DEBUG replicate_api.py: Возвращаем URL из списка: {result[:100]}...")
            return result
        
        result = str(output)
        print(f"DEBUG replicate_api.py: Возвращаем URL: {result[:100]}...")
        return result
        
    except Exception as e:
        print(f"DEBUG replicate_api.py: ОШИБКА при генерации - {e}")
        raise e
