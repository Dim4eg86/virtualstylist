import replicate
import os

async def generate_vton_image(human_url, garment_url):
    # API токен будет браться из переменных окружения Railway
    output = await replicate.async_run(
        "subhash25rawat/flux-vton:a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199",
        input={
            "image": human_url,
            "garment": garment_url,
            "description": "Stylish outfit",
            "vton_mode": "Overall"
        }
    )
    return output