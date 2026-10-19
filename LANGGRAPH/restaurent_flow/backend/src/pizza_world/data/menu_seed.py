"""Structured menu extracted from Pizza_World_Menu_Text.pdf (Pizza World, Sahiwal)."""

from __future__ import annotations

# (name, category, size, price, description)
MENU_ROWS: list[tuple[str, str, str | None, float, str | None]] = [
    # Traditional Flavours — Small 400 / Medium 900 / Large 1150 (Hot N Spicy shares sizes)
    ("Chicken Tikka", "traditional", "Small", 400.0, "Traditional flavour pizza, small size"),
    ("Chicken Tikka", "traditional", "Medium", 900.0, "Traditional flavour pizza, medium size"),
    ("Chicken Tikka", "traditional", "Large", 1150.0, "Traditional flavour pizza, large size"),
    ("Chicken Fajita", "traditional", "Small", 400.0, "Traditional flavour pizza, small size"),
    ("Chicken Fajita", "traditional", "Medium", 900.0, "Traditional flavour pizza, medium size"),
    ("Chicken Fajita", "traditional", "Large", 1150.0, "Traditional flavour pizza, large size"),
    ("Chicken Supreme", "traditional", "Small", 400.0, "Traditional flavour pizza, small size"),
    ("Chicken Supreme", "traditional", "Medium", 900.0, "Traditional flavour pizza, medium size"),
    ("Chicken Supreme", "traditional", "Large", 1150.0, "Traditional flavour pizza, large size"),
    ("Hot N Spicy", "traditional", "Small", 400.0, "Traditional flavour pizza, small size"),
    ("Hot N Spicy", "traditional", "Medium", 900.0, "Traditional flavour pizza, medium size"),
    ("Hot N Spicy", "traditional", "Large", 1150.0, "Traditional flavour pizza, large size"),
    # World Specials — Small 450 / Medium 1000 / Large 1300
    ("World Special", "world_special", "Small", 450.0, "World special pizza, small size"),
    ("World Special", "world_special", "Medium", 1000.0, "World special pizza, medium size"),
    ("World Special", "world_special", "Large", 1300.0, "World special pizza, large size"),
    ("Malai Boti", "world_special", "Small", 450.0, "World special pizza, small size"),
    ("Malai Boti", "world_special", "Medium", 1000.0, "World special pizza, medium size"),
    ("Malai Boti", "world_special", "Large", 1300.0, "World special pizza, medium size"),
    ("Bone Fire", "world_special", "Small", 450.0, "World special pizza, small size"),
    ("Bone Fire", "world_special", "Medium", 1000.0, "World special pizza, medium size"),
    ("Bone Fire", "world_special", "Large", 1300.0, "World special pizza, large size"),
    ("Mughlai", "world_special", "Small", 450.0, "World special pizza, small size"),
    ("Mughlai", "world_special", "Medium", 1000.0, "World special pizza, medium size"),
    ("Mughlai", "world_special", "Large", 1300.0, "World special pizza, large size"),
    # Stuffed / Crust
    ("Behari Kabab", "stuffed", "Medium", 1250.0, "Stuff crust pizza with behari kabab, medium"),
    ("Crown Crust", "stuffed", "Large", 1600.0, "Crown crust pizza, large"),
    (
        "Chicken & Cheese Stuff",
        "stuffed",
        "Medium",
        1250.0,
        "Stuffed pizza with chicken and cheese, medium",
    ),
    ("Kabab Stuff", "stuffed", "Large", 1600.0, "Stuffed pizza with kabab, large"),
    # Appetizers
    ("Hot Wings", "appetizers", "5 pcs", 350.0, "Hot wings, 5 pieces"),
    ("Hot Wings", "appetizers", "10 pcs", 650.0, "Hot wings, 10 pieces"),
    ("French Fries", "appetizers", "Half", 250.0, "French fries, half portion"),
    ("French Fries", "appetizers", "Full", 400.0, "French fries, full portion"),
    ("Loaded Fries", "appetizers", "Full", 600.0, "Loaded fries, full portion"),
    ("Calazone Chunks", "appetizers", None, 900.0, "Calazone chunks"),
    ("Nuggets", "appetizers", "5 pcs", 300.0, "Chicken nuggets, 5 pieces"),
    ("Nuggets", "appetizers", "10 pcs", 580.0, "Chicken nuggets, 10 pieces"),
    ("Hot Shots", "appetizers", "10 pcs", 300.0, "Hot shots, 10 pieces"),
    ("Hot Shots", "appetizers", "20 pcs", 580.0, "Hot shots, 20 pieces"),
    ("Oven Baked Wings", "appetizers", "5 pcs", 350.0, "Oven baked wings, 5 pieces"),
    ("Oven Baked Wings", "appetizers", "10 pcs", 650.0, "Oven baked wings, 10 pieces"),
    ("Flaming Wings", "appetizers", "5 pcs", 350.0, "Flaming wings, 5 pieces"),
    ("Flaming Wings", "appetizers", "10 pcs", 650.0, "Flaming wings, 10 pieces"),
    # Pasta
    ("World Special Pasta", "pasta", "Half", 400.0, "World special pasta, half"),
    ("World Special Pasta", "pasta", "Full", 700.0, "World special pasta, full"),
    ("Crunchy Pasta", "pasta", None, 0.0, "Crunchy pasta - price not clearly shown on menu"),
    # Shawarma
    ("Malai Boti Shawarma", "shawarma", None, 250.0, "Malai boti shawarma"),
    ("Chicken Shawarma", "shawarma", None, 200.0, "Chicken shawarma"),
    ("Chicken Cheese Shawarma", "shawarma", None, 250.0, "Chicken cheese shawarma"),
    ("Zinger Shawarma", "shawarma", None, 300.0, "Zinger shawarma"),
    ("Chicken Roll Paratha", "shawarma", None, 300.0, "Chicken roll paratha"),
    ("Zinger Roll Paratha", "shawarma", None, 350.0, "Zinger roll paratha"),
    # Rolls & Platter
    ("World Special Platter", "rolls", None, 850.0, "World special platter"),
    ("Spin Rolls", "rolls", None, 450.0, "Spin rolls"),
    ("Malai Rolls", "rolls", None, 550.0, "Malai rolls"),
    # Pizza snacks
    ("Pizza Burger", "snacks", None, 600.0, "Pizza burger"),
    ("Pizza Stacker", "snacks", None, 750.0, "Pizza stacker"),
    ("Cheese Stick", "snacks", None, 400.0, "Cheese stick"),
    # Burgers
    ("Zinger Burger", "burgers", None, 350.0, "Zinger burger"),
    ("Patty Burger", "burgers", None, 300.0, "Patty burger"),
    ("Double Dacker", "burgers", None, 550.0, "Double dacker burger"),
    # Deals
    ("Deal 1", "deals", None, 650.0, "1 Small Pizza, 1 Regular Fries, 1 Regular Drink"),
    ("Deal 2", "deals", None, 1800.0, "1 Large Pizza (Traditional), 10 Hot Wings, 1 Liter Drink"),
    ("Deal 3", "deals", None, 1450.0, "1 Medium Pizza (Traditional), Half Pasta, 1 Liter Drink"),
    ("Deal 4", "deals", None, 1800.0, "3 Zinger Burgers, 2 Patty Burgers, 1.5 Liter Cold Drink"),
    ("Deal 5", "deals", None, 2400.0, "2 Large Pizzas (Traditional), 1.5 Liter Drink"),
    ("Deal 6", "deals", None, 1900.0, "2 Medium Pizzas (Traditional), 1.5 Liter Drink"),
]

RESTAURANT_INFO = {
    "name": "PIZZA WORLD",
    "tagline": "Menu & Prices - Grand Opening Menu, Traditional Flavours",
    "timing": "3 PM to 2 AM",
    "offer": "10% off for 3 days - 4, 5 & 6 June 2026",
    "delivery": "Free Home Delivery",
    "phone": "0320-8372155 / 0306-1211813",
    "address": "New Usman Hotel, Opp. Arifwala Road, Sahiwal",
}
