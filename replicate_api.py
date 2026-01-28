import replicate
import os

async def generate_vton_image(human_url, garment_url, category):
    # IDM-VTON - быстрая модель (20 сек вместо 5-7 минут)
    model_version = "cuuupid/idm-vton:906425dbca90663ff5427624839572cc56ea7d380343d13e2a4c4b09d3f0c30f"
    
    print(f"DEBUG: Запуск генерации IDM-VTON. Категория: {category}")
    
    # Маппинг ТВОИХ категорий на категории IDM-VTON
    category_mapping = {
        "верх": "upper_body",
        "низ": "lower_body",
        "платье": "dresses",
        # На всякий случай английские варианты
        "upper": "upper_body",
        "lower": "lower_body",
        "dress": "dresses",
        "dresses": "dresses"
    }
    
    # Определяем категорию для модели (по умолчанию верх)
    model_category = category_mapping.get(category.lower(), "upper_body")
    
    print(f"DEBUG: Маппинг категории '{category}' -> '{model_category}'")
    
    try:
        output = await replicate.async_run(
            model_version,
            input={
                "human_img": human_url,
                "garm_img": garment_url,
                "garment_des": "High quality clothing item",
                "category": model_category,
                "n_samples": 1,
                "n_steps": 20,      # 20 = быстро (~20 сек), 30 = лучше качество (~30 сек)
                "image_scale": 2,
                "seed": -1
            }
        )
        
        print(f"DEBUG: IDM-VTON успешно завершен. Тип output: {type(output)}")
        
        if isinstance(output, list):
            return str(output[0])
        return str(output)
    except Exception as e:
        print(f"DEBUG: Ошибка в Replicate IDM-VTON: {e}")
        raise e
