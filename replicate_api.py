import replicate
import os

async def generate_vton_image(human_url, garment_url, category):
    # Используем актуальную версию модели Flux-VTON
    model_version = "subhash25rawat/flux-vton:a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199"
    
    print(f"DEBUG: Запуск генерации. Категория: {category}")
    
    try:
        output = await replicate.async_run(
            model_version,
            input={
                "image": human_url,
                "garment": garment_url,
                "task": "vton",
                "part": category,     # Передаем выбранную юзером категорию
                "category": category,
                "description": "High quality photo, stylish outfit"
            }
        )
        
        if isinstance(output, list):
            return str(output[0])
        return str(output)
    except Exception as e:
        print(f"DEBUG: Ошибка в Replicate: {e}")
        raise e
