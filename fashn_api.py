import fal_client
import os
import requests
from io import BytesIO
from PIL import Image

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
        print(f"DEBUG fashn_api.py: Загружаем изображения с URL")
        
        # Загружаем изображения
        print(f"DEBUG fashn_api.py: Загружаем human_url: {human_url[:100]}")
        human_response = requests.get(human_url)
        human_image = Image.open(BytesIO(human_response.content))
        
        print(f"DEBUG fashn_api.py: Загружаем garment_url: {garment_url[:100]}")
        garment_response = requests.get(garment_url)
        garment_image = Image.open(BytesIO(garment_response.content))
        
        # Сохраняем временно
        human_path = "/tmp/human_temp.jpg"
        garment_path = "/tmp/garment_temp.jpg"
        
        human_image.save(human_path, "JPEG")
        garment_image.save(garment_path, "JPEG")
        
        print(f"DEBUG fashn_api.py: Изображения сохранены, запускаем FASHN v1.5")
        
        # Вызов FASHN v1.5 с файлами
        result = fal_client.run(
            "fal-ai/fashn/tryon/v1.5",
            arguments={
                "model_image": open(human_path, "rb"),
                "garment_image": open(garment_path, "rb"),
                "category": fashn_category
            }
        )
        
        print(f"DEBUG fashn_api.py: Генерация завершена успешно")
        print(f"DEBUG fashn_api.py: Результат: {result}")
        
        # Извлекаем URL изображения
        if "images" in result and len(result["images"]) > 0:
            image_url = result["images"][0]["url"]
            print(f"DEBUG fashn_api.py: Возвращаем URL: {image_url[:100]}...")
            
            # Очищаем временные файлы
            os.remove(human_path)
            os.remove(garment_path)
            
            return image_url
        else:
            raise Exception("No images in result")
        
    except Exception as e:
        print(f"DEBUG fashn_api.py: ОШИБКА при генерации - {e}")
        # Очищаем временные файлы в случае ошибки
        try:
            if os.path.exists("/tmp/human_temp.jpg"):
                os.remove("/tmp/human_temp.jpg")
            if os.path.exists("/tmp/garment_temp.jpg"):
                os.remove("/tmp/garment_temp.jpg")
        except:
            pass
        raise e
