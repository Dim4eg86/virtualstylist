import replicate
import os

async def generate_vton_image(human_url, garment_url):
    model_version = "subhash25rawat/flux-vton:a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199"
    
    print(f"DEBUG: Отправка запроса в Replicate...")
    print(f"DEBUG: Human URL: {human_url[:50]}...")
    print(f"DEBUG: Garment URL: {garment_url[:50]}...")

    try:
        # Важно: используем await, так как функция асинхронная
        output = await replicate.async_run(
            model_version,
            input={
                "image": human_url,
                "garment": garment_url,
                "task": "vton",
                "part": "upper_body",
                "category": "upper_body",
                "description": "Stylish clothing"
            }
        )
        print(f"DEBUG: Ответ от Replicate получен: {output}")
        
        # Если пришел список объектов (часто бывает у Flux)
        if isinstance(output, list):
            return str(output[0])
        return str(output)
        
    except Exception as e:
        print(f"DEBUG: ОШИБКА REPLICATE: {e}")
        raise e
