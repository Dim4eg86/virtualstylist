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
        
        print(f"DEBUG fashn_api.py: Загружаем garment_url: {garment_url[:100]}")
        garment_response = requests.get(garment_url)
        
        # Сохраняем временно
        human_path = "/tmp/human_temp.jpg"
        garment_path = "/tmp/garment_temp.jpg"
        
        with open(human_path, "wb") as f:
            f.write(human_response.content)
        
        with open(garment_path, "wb") as f:
            f.write(garment_response.content)
        
        print(f"DEBUG fashn_api.py: Изображения сохранены, загружаем в FAL.AI")
        
        # Загружаем файлы в FAL.AI
        human_fal_url = fal_client.upload_file(human_path)
        garment_fal_url = fal_client.upload_file(garment_path)
        
        print(f"DEBUG fashn_api.py: Файлы загружены, запускаем FASHN v1.5")
        print(f"DEBUG fashn_api.py: human_fal_url: {human_fal_url}")
        print(f"DEBUG fashn_api.py: garment_fal_url: {garment_fal_url}")
        
        # Вызов FASHN v1.5 с загруженными URL
        result = fal_client.run(
            "fal-ai/fashn/tryon/v1.5",
            arguments={
                "model_image_url": human_fal_url,
                "garment_image_url": garment_fal_url,
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
