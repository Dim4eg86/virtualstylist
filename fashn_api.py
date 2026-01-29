import fal_client
import os

# API ключ для FAL.AI
FAL_KEY = "3f5f655d-ddeb-4b7d-9d61-cde5727ef530:cb7a705887edfa28d546cab531329fbb"
os.environ["FAL_KEY"] = FAL_KEY

async def generate_vton_fashn(human_url, garment_url, category):
    """
    Генерация виртуальной примерки через FASHN v1.5 (FAL.AI)
    
    Используется для платьев с категорией "one-pieces"
    
    Args:
        human_url: URL фото человека
        garment_url: URL фото одежды
        category: Категория одежды ("верх", "низ", "платье")
    
    Returns:
        str: URL сгенерированного изображения
    """
    print(f"DEBUG fashn_api.py: Получена категория='{category}'")
    
    # Маппинг категорий на FASHN категории
    category_mapping = {
        "верх": "tops",
        "низ": "bottoms",
        "платье": "one-pieces",  # ← КЛЮЧЕВОЕ! Для платьев целиком!
        # На всякий случай английские варианты
        "tops": "tops",
        "bottoms": "bottoms",
        "dresses": "one-pieces",
        "one-pieces": "one-pieces"
    }
    
    fashn_category = category_mapping.get(category.lower(), "tops")
    
    print(f"DEBUG fashn_api.py: Маппинг '{category}' -> '{fashn_category}'")
    
    try:
        print(f"DEBUG fashn_api.py: Запускаем FASHN v1.5 через FAL.AI")
        
        # Вызов FASHN v1.5
        result = fal_client.run(
            "fal-ai/fashn/tryon/v1.5",
            arguments={
                "person_image_url": human_url,
                "garment_image_url": garment_url,
                "category": fashn_category
            }
        )
        
        print(f"DEBUG fashn_api.py: Генерация завершена успешно")
        print(f"DEBUG fashn_api.py: Результат: {result}")
        
        # Извлекаем URL изображения
        if "images" in result and len(result["images"]) > 0:
            image_url = result["images"][0]["url"]
            print(f"DEBUG fashn_api.py: Возвращаем URL: {image_url[:100]}...")
            return image_url
        else:
            raise Exception("No images in result")
        
    except Exception as e:
        print(f"DEBUG fashn_api.py: ОШИБКА при генерации - {e}")
        raise e
