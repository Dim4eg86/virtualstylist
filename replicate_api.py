import replicate
import os

async def generate_vton_image(human_url, garment_url, category):
    """
    Генерация виртуальной примерки через Flux-Fill-Redux-Try-On
    
    Поддерживает категорию "overall" для платьев целиком!
    
    Args:
        human_url: URL фото человека
        garment_url: URL фото одежды
        category: Категория одежды ("верх", "низ", "платье")
    
    Returns:
        str: URL сгенерированного изображения
    """
    # Flux-Fill-Redux - поддерживает платья через "overall"!
    model_name = "cedoysch/flux-fill-redux-try-on"
    
    print(f"DEBUG replicate_api.py (Flux-Redux): Получена категория='{category}'")
    
    # Маппинг русских категорий на Flux-Redux категории
    category_mapping = {
        "верх": "upper",
        "низ": "lower",
        "платье": "overall",  # ← КЛЮЧЕВОЕ! Платья целиком!
        # На всякий случай английские варианты
        "upper": "upper",
        "lower": "lower",
        "dresses": "overall"
    }
    
    model_category = category_mapping.get(category.lower(), "upper")
    
    print(f"DEBUG replicate_api.py (Flux-Redux): Маппинг '{category}' -> '{model_category}'")
    
    try:
        print(f"DEBUG replicate_api.py (Flux-Redux): Запускаем Flux-Fill-Redux-Try-On")
        
        output = await replicate.async_run(
            model_name,
            input={
                "person_image": human_url,    # Фото человека
                "cloth_image": garment_url,    # Фото одежды
                "clot_type": model_category    # Категория: upper/lower/overall
            }
        )
        
        print(f"DEBUG replicate_api.py (Flux-Redux): Генерация завершена успешно. Тип output: {type(output)}")
        
        # Обработка результата
        if isinstance(output, list):
            result = str(output[0])
            print(f"DEBUG replicate_api.py (Flux-Redux): Возвращаем URL из списка: {result[:100]}...")
            return result
        
        result = str(output)
        print(f"DEBUG replicate_api.py (Flux-Redux): Возвращаем URL: {result[:100]}...")
        return result
        
    except Exception as e:
        print(f"DEBUG replicate_api.py (Flux-Redux): ОШИБКА при генерации - {e}")
        raise e
