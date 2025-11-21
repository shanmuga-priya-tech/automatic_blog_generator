import os
import time
import random
import requests
from slugify import slugify
from openai import AzureOpenAI

# Load clients
prompt_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_PROMPT_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_PROMPT_ENDPOINT"),
    api_version=os.getenv("AZURE_API_VERSION")
)

image_client = AzureOpenAI(
    api_key=os.getenv("AZURE_IMAGE_API_KEY"),
    azure_endpoint=os.getenv("AZURE_IMAGE_ENDPOINT"),
    api_version=os.getenv("AZURE_IMAGE_API_VERSION")
)

# Load base prompt
with open("base_prompt.txt", "r", encoding="utf-8") as f:
    BASE_PROMPT = f.read().strip()


def generate_images_for_blog(blog_title, blog_content, num_images=4):
    """
    Creates 1 image for each blog.
    Uses blog content + base_prompt & injects brand name automatically.
    """

    folder = f"output/images/{slugify(blog_title)}"
    os.makedirs(folder, exist_ok=True)

    for i in range(1, num_images + 1):

        # Fill dynamic variation template
        raw_prompt = BASE_PROMPT.format(
            time_of_day=random.choice(["morning", "evening", "golden hour"]),
            scene_type="real Indian rooftop solar installation",
            location_detail="residential home with solar panels",
            examples_of_setting="small street shops nearby",
            human_activity="technician installing solar panels",
            extra_elements="birds flying above"
        )

        # Combine blog content (to match theme)
        merged_prompt = (
            f"Blog context:\n{blog_content[:1200]}\n\n"
            f"Scene:\n{raw_prompt}\n\n"
            f"Include GharGharSolar brand in a natural way."
        )


        # Generate image
        response = image_client.images.generate(
            model="dall-e-3",
            prompt=merged_prompt,
            size="1792x1024"
        )

        # Download image
        url = response.data[0].url
        img_data = requests.get(url).content

        # Save image
        img_name = os.path.join(folder, f"image_{i}.png")
        with open(img_name, "wb") as f:
            f.write(img_data)

        print(f"Saved → {img_name}")


        time.sleep(2)  # avoid rate limit

    return folder
