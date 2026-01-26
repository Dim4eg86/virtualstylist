import replicate
import os

async def generate_vton_image(human_url, garment_url):
    # Указываем актуальную версию модели
    model_version = "subhash25rawat/flux-vton:a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199"
    
    try:
        output = await replicate.async_run(
            model_version,
            input={
                "image": human_url,
                "garment": garment_url,
                "task": "vton",             # Добавляем задачу
                "part": "upper_body",       # По умолчанию - верх (самое частое)
                "category": "upper_body",    # На всякий случай дублируем в category
                "description": "Stylish clothing",
                "guidance_scale": 3.5,
                "num_inference_steps": 30
            }
        )
        # Нейросеть возвращает список или один URL
        if isinstance(output, list):
            return output[0]
        return output
    except Exception as e:
        print(f"Ошибка Replicate API: {e}")
        raise e
