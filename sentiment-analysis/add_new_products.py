#!/usr/bin/env python3
import json
from pathlib import Path

DATA_DIR = Path('../src/data')

NEW_PRODUCTS = {
    "motherboards.json": [
        {
            "rank": 6,
            "name": "ASRock B650 PG Lightning",
            "brand": "ASRock",
            "model": "B650 PG Lightning",
            "priceRange": "$160-$180",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=ASRock+B650+PG+Lightning", "newegg": "https://www.newegg.com/p/pl?d=ASRock+B650+PG+Lightning"},
            "specs": {"socket": "AM5", "formFactor": "ATX", "chipset": "AMD B650"},
            "tags": ["AM5", "Value", "ATX"]
        },
        {
            "rank": 7,
            "name": "Gigabyte B650 Gaming X AX",
            "brand": "Gigabyte",
            "model": "B650 Gaming X AX",
            "priceRange": "$170-$190",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Gigabyte+B650+Gaming+X+AX", "newegg": "https://www.newegg.com/p/pl?d=Gigabyte+B650+Gaming+X+AX"},
            "specs": {"socket": "AM5", "formFactor": "ATX", "chipset": "AMD B650"},
            "tags": ["AM5", "Mid-Range", "Wi-Fi"]
        },
        {
            "rank": 8,
            "name": "ASUS TUF Gaming B650-Plus WiFi",
            "brand": "ASUS",
            "model": "TUF B650-Plus",
            "priceRange": "$190-$210",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=ASUS+TUF+Gaming+B650-Plus+WiFi", "newegg": "https://www.newegg.com/p/pl?d=ASUS+TUF+B650-Plus"},
            "specs": {"socket": "AM5", "formFactor": "ATX", "chipset": "AMD B650"},
            "tags": ["AM5", "TUF", "Wi-Fi"]
        },
        {
            "rank": 9,
            "name": "ASRock X870 Pro RS",
            "brand": "ASRock",
            "model": "X870 Pro RS",
            "priceRange": "$200-$220",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=ASRock+X870+Pro+RS", "newegg": "https://www.newegg.com/p/pl?d=ASRock+X870+Pro+RS"},
            "specs": {"socket": "AM5", "formFactor": "ATX", "chipset": "AMD X870"},
            "tags": ["AM5", "USB4", "Value"]
        },
        {
            "rank": 10,
            "name": "ASUS ROG Strix X670E-I Gaming WiFi",
            "brand": "ASUS",
            "model": "Strix X670E-I",
            "priceRange": "$320-$360",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=ASUS+ROG+Strix+X670E-I+Gaming+WiFi", "newegg": "https://www.newegg.com/p/pl?d=Strix+X670E-I"},
            "specs": {"socket": "AM5", "formFactor": "Mini-ITX", "chipset": "AMD X670E"},
            "tags": ["AM5", "SFF", "Premium", "Mini-ITX"]
        }
    ],
    "cases.json": [
        {
            "rank": 7,
            "name": "NZXT H6 Flow",
            "brand": "NZXT",
            "model": "H6 Flow",
            "priceRange": "$100-$115",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=NZXT+H6+Flow", "newegg": "https://www.newegg.com/p/pl?d=NZXT+H6+Flow"},
            "specs": {"formFactor": "ATX Mid-Tower", "dimensions": "415 x 287 x 435 mm"},
            "tags": ["Airflow", "Dual-Chamber", "Aesthetics"]
        },
        {
            "rank": 8,
            "name": "Fractal Design North",
            "brand": "Fractal Design",
            "model": "North",
            "priceRange": "$130-$150",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Fractal+Design+North", "newegg": "https://www.newegg.com/p/pl?d=Fractal+Design+North"},
            "specs": {"formFactor": "ATX Mid-Tower", "dimensions": "447 x 215 x 469 mm"},
            "tags": ["Wood", "Premium", "Design", "Reddit Favorite"]
        },
        {
            "rank": 9,
            "name": "Lian Li O11 Dynamic EVO",
            "brand": "Lian Li",
            "model": "O11D EVO",
            "priceRange": "$150-$170",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Lian+Li+O11+Dynamic+EVO", "newegg": "https://www.newegg.com/p/pl?d=Lian+Li+O11+Dynamic+EVO"},
            "specs": {"formFactor": "ATX Mid-Tower", "dimensions": "465 x 285 x 459 mm"},
            "tags": ["Panoramic", "Modular", "Watercooling"]
        },
        {
            "rank": 10,
            "name": "Montech King 95 Pro",
            "brand": "Montech",
            "model": "King 95 Pro",
            "priceRange": "$110-$130",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Montech+King+95+Pro", "newegg": "https://www.newegg.com/p/pl?d=Montech+King+95+Pro"},
            "specs": {"formFactor": "ATX Mid-Tower", "dimensions": "475 x 300 x 442 mm"},
            "tags": ["Value", "Panoramic", "Included Fans"]
        }
    ],
    "coolers.json": [
        {
            "rank": 5,
            "name": "Thermalright Phantom Spirit 120 EVO",
            "brand": "Thermalright",
            "model": "Phantom Spirit 120 EVO",
            "priceRange": "$42-$48",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Thermalright+Phantom+Spirit+120+EVO", "newegg": "https://www.newegg.com/p/pl?d=Phantom+Spirit+EVO"},
            "specs": {"type": "Air Cooler", "tdp": "280W"},
            "tags": ["Dual-Tower", "Best Value", "Silent"]
        },
        {
            "rank": 6,
            "name": "Arctic Liquid Freezer III 360",
            "brand": "Arctic",
            "model": "Liquid Freezer III 360",
            "priceRange": "$110-$130",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Arctic+Liquid+Freezer+III+360", "newegg": "https://www.newegg.com/p/pl?d=Liquid+Freezer+III"},
            "specs": {"type": "AIO Liquid Cooler", "tdp": "340W"},
            "tags": ["AIO", "Silent", "Premium Performance"]
        },
        {
            "rank": 7,
            "name": "Noctua NH-U12S Redux",
            "brand": "Noctua",
            "model": "NH-U12S Redux",
            "priceRange": "$45-$55",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Noctua+NH-U12S+Redux", "newegg": "https://www.newegg.com/p/pl?d=NH-U12S+Redux"},
            "specs": {"type": "Air Cooler", "tdp": "150W"},
            "tags": ["Single-Tower", "Low-Profile", "Reliable"]
        },
        {
            "rank": 8,
            "name": "Thermalright Assassin X 120 Refined SE",
            "brand": "Thermalright",
            "model": "Assassin X 120",
            "priceRange": "$18-$22",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Thermalright+Assassin+X+120+Refined+SE", "newegg": "https://www.newegg.com/p/pl?d=Assassin+X+120"},
            "specs": {"type": "Air Cooler", "tdp": "180W"},
            "tags": ["Budget King", "Single-Tower"]
        },
        {
            "rank": 9,
            "name": "NZXT Kraken Elite 360",
            "brand": "NZXT",
            "model": "Kraken Elite 360",
            "priceRange": "$260-$290",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=NZXT+Kraken+Elite+360", "newegg": "https://www.newegg.com/p/pl?d=Kraken+Elite+360"},
            "specs": {"type": "AIO Liquid Cooler", "tdp": "320W"},
            "tags": ["LCD Screen", "Premium", "AIO"]
        },
        {
            "rank": 10,
            "name": "Deepcool LT720 360mm AIO",
            "brand": "Deepcool",
            "model": "LT720",
            "priceRange": "$120-$140",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Deepcool+LT720", "newegg": "https://www.newegg.com/p/pl?d=Deepcool+LT720"},
            "specs": {"type": "AIO Liquid Cooler", "tdp": "300W"},
            "tags": ["AIO", "Aesthetics", "Infinity Mirror"]
        }
    ],
    "psus.json": [
        {
            "rank": 5,
            "name": "MSI MAG A850GL",
            "brand": "MSI",
            "model": "A850GL",
            "priceRange": "$100-$120",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=MSI+MAG+A850GL", "newegg": "https://www.newegg.com/p/pl?d=MSI+MAG+A850GL"},
            "specs": {"wattage": "850W", "efficiency": "80+ Gold", "modular": "Full Modular"},
            "tags": ["ATX 3.0", "PCIe 5.0", "Value"]
        },
        {
            "rank": 6,
            "name": "Corsair SF750 Platinum",
            "brand": "Corsair",
            "model": "SF750",
            "priceRange": "$160-$180",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Corsair+SF750+Platinum", "newegg": "https://www.newegg.com/p/pl?d=SF750+Platinum"},
            "specs": {"wattage": "750W", "efficiency": "80+ Platinum", "modular": "Full Modular SFX"},
            "tags": ["SFX", "SFF Legendary", "Platinum"]
        },
        {
            "rank": 7,
            "name": "Be Quiet! Pure Power 12 M 850W",
            "brand": "be quiet!",
            "model": "Pure Power 12 M 850W",
            "priceRange": "$115-$130",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Be+Quiet+Pure+Power+12+M+850W", "newegg": "https://www.newegg.com/p/pl?d=Pure+Power+12+M+850W"},
            "specs": {"wattage": "850W", "efficiency": "80+ Gold", "modular": "Full Modular"},
            "tags": ["Silent", "ATX 3.0", "Gold"]
        },
        {
            "rank": 8,
            "name": "EVGA SuperNOVA 850 GT",
            "brand": "EVGA",
            "model": "850 GT",
            "priceRange": "$110-$130",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=EVGA+SuperNOVA+850+GT", "newegg": "https://www.newegg.com/p/pl?d=EVGA+850+GT"},
            "specs": {"wattage": "850W", "efficiency": "80+ Gold", "modular": "Full Modular"},
            "tags": ["Value", "Reliable", "Gold"]
        },
        {
            "rank": 9,
            "name": "Corsair RM750e ATX 3.0",
            "brand": "Corsair",
            "model": "RM750e",
            "priceRange": "$99-$110",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Corsair+RM750e", "newegg": "https://www.newegg.com/p/pl?d=Corsair+RM750e"},
            "specs": {"wattage": "750W", "efficiency": "80+ Gold", "modular": "Full Modular"},
            "tags": ["ATX 3.0", "Budget", "Gold"]
        },
        {
            "rank": 10,
            "name": "Seasonic Vertex GX-1000",
            "brand": "Seasonic",
            "model": "Vertex GX-1000",
            "priceRange": "$200-$220",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Seasonic+Vertex+GX-1000", "newegg": "https://www.newegg.com/p/pl?d=Vertex+GX-1000"},
            "specs": {"wattage": "1000W", "efficiency": "80+ Gold", "modular": "Full Modular"},
            "tags": ["Premium", "ATX 3.0", "1000W"]
        }
    ],
    "ram.json": [
        {
            "rank": 4,
            "name": "Teamgroup T-Force Delta RGB DDR5-6000 CL30",
            "brand": "Teamgroup",
            "model": "Delta RGB DDR5",
            "priceRange": "$100-$115",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Teamgroup+T-Force+Delta+RGB+DDR5-6000+CL30", "newegg": "https://www.newegg.com/p/pl?d=T-Force+Delta+DDR5"},
            "specs": {"capacity": "32GB (2x16GB)", "speed": "6000 MT/s", "type": "DDR5 CL30"},
            "tags": ["RGB", "AM5 Sweet Spot"]
        },
        {
            "rank": 5,
            "name": "Corsair Vengeance RGB DDR5-6000 CL30",
            "brand": "Corsair",
            "model": "Vengeance RGB DDR5",
            "priceRange": "$115-$130",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Corsair+Vengeance+RGB+DDR5-6000+CL30", "newegg": "https://www.newegg.com/p/pl?d=Vengeance+RGB+DDR5"},
            "specs": {"capacity": "32GB (2x16GB)", "speed": "6000 MT/s", "type": "DDR5 CL30"},
            "tags": ["RGB", "Corsair iCUE"]
        },
        {
            "rank": 6,
            "name": "G.Skill Flare X5 DDR5-6000 CL30",
            "brand": "G.Skill",
            "model": "Flare X5 DDR5",
            "priceRange": "$95-$105",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=G.Skill+Flare+X5+DDR5-6000+CL30", "newegg": "https://www.newegg.com/p/pl?d=Flare+X5+DDR5"},
            "specs": {"capacity": "32GB (2x16GB)", "speed": "6000 MT/s", "type": "DDR5 CL30"},
            "tags": ["Low-Profile", "AMD EXPO Optimized"]
        },
        {
            "rank": 7,
            "name": "Crucial Pro DDR5-5600",
            "brand": "Crucial",
            "model": "Crucial Pro DDR5",
            "priceRange": "$85-$95",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Crucial+Pro+DDR5-5600", "newegg": "https://www.newegg.com/p/pl?d=Crucial+Pro+DDR5"},
            "specs": {"capacity": "32GB (2x16GB)", "speed": "5600 MT/s", "type": "DDR5 CL46"},
            "tags": ["Non-RGB", "Reliable", "Enterprise"]
        },
        {
            "rank": 8,
            "name": "Teamgroup T-Create Classic DDR5-6000 CL30",
            "brand": "Teamgroup",
            "model": "T-Create Classic",
            "priceRange": "$95-$105",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Teamgroup+T-Create+Classic+DDR5-6000+CL30", "newegg": "https://www.newegg.com/p/pl?d=T-Create+Classic"},
            "specs": {"capacity": "32GB (2x16GB)", "speed": "6000 MT/s", "type": "DDR5 CL30"},
            "tags": ["Creator", "Minimalist", "Sleek"]
        },
        {
            "rank": 9,
            "name": "Patriot Viper Venom DDR5-6400 CL32",
            "brand": "Patriot",
            "model": "Viper Venom DDR5",
            "priceRange": "$100-$120",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Patriot+Viper+Venom+DDR5-6400", "newegg": "https://www.newegg.com/p/pl?d=Viper+Venom+DDR5"},
            "specs": {"capacity": "32GB (2x16GB)", "speed": "6400 MT/s", "type": "DDR5 CL32"},
            "tags": ["High-Speed", "Enthusiast"]
        },
        {
            "rank": 10,
            "name": "Silicon Power Zenith DDR5-6000 CL30",
            "brand": "Silicon Power",
            "model": "SP Zenith DDR5",
            "priceRange": "$80-$90",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Silicon+Power+Zenith+DDR5-6000", "newegg": "https://www.newegg.com/p/pl?d=SP+Zenith+DDR5"},
            "specs": {"capacity": "32GB (2x16GB)", "speed": "6000 MT/s", "type": "DDR5 CL30"},
            "tags": ["Budget King", "Value", "Low-Profile"]
        }
    ],
    "ssds.json": [
        {
            "rank": 5,
            "name": "WD Black SN850X",
            "brand": "WD",
            "model": "SN850X",
            "priceRange": "$140-$160",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=WD+Black+SN850X", "newegg": "https://www.newegg.com/p/pl?d=WD+Black+SN850X"},
            "specs": {"capacity": "2TB", "interface": "PCIe Gen 4 x4", "formFactor": "M.2 2280"},
            "tags": ["DRAM Cache", "Flagship Performance", "Gaming Favorite"]
        },
        {
            "rank": 6,
            "name": "Crucial T500",
            "brand": "Crucial",
            "model": "T500",
            "priceRange": "$120-$145",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Crucial+T500", "newegg": "https://www.newegg.com/p/pl?d=Crucial+T500"},
            "specs": {"capacity": "2TB", "interface": "PCIe Gen 4 x4", "formFactor": "M.2 2280"},
            "tags": ["DRAM Cache", "Power Efficient"]
        },
        {
            "rank": 7,
            "name": "Crucial P3 Plus",
            "brand": "Crucial",
            "model": "P3 Plus",
            "priceRange": "$90-$110",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Crucial+P3+Plus", "newegg": "https://www.newegg.com/p/pl?d=Crucial+P3+Plus"},
            "specs": {"capacity": "2TB", "interface": "PCIe Gen 4 x4", "formFactor": "M.2 2280"},
            "tags": ["Value Secondary", "DRAM-less"]
        },
        {
            "rank": 8,
            "name": "Kingston KC3000",
            "brand": "Kingston",
            "model": "KC3000",
            "priceRange": "$130-$150",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Kingston+KC3000", "newegg": "https://www.newegg.com/p/pl?d=Kingston+KC3000"},
            "specs": {"capacity": "2TB", "interface": "PCIe Gen 4 x4", "formFactor": "M.2 2280"},
            "tags": ["DRAM Cache", "Workhorse", "Consistent"]
        },
        {
            "rank": 9,
            "name": "Teamgroup MP44L",
            "brand": "Teamgroup",
            "model": "MP44L",
            "priceRange": "$85-$95",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Teamgroup+MP44L", "newegg": "https://www.newegg.com/p/pl?d=Teamgroup+MP44L"},
            "specs": {"capacity": "2TB", "interface": "PCIe Gen 4 x4", "formFactor": "M.2 2280"},
            "tags": ["Reddit Budget Favorite", "DRAM-less", "Value"]
        },
        {
            "rank": 10,
            "name": "Lexar NM790",
            "brand": "Lexar",
            "model": "NM790",
            "priceRange": "$115-$130",
            "mentions": 0, "positiveReviews": 0, "negativeReviews": 0, "neutralReviews": 0, "recommendationRate": 0.0,
            "redditQuotes": [],
            "affiliateLinks": {"amazon": "https://www.amazon.com/s?k=Lexar+NM790", "newegg": "https://www.newegg.com/p/pl?d=Lexar+NM790"},
            "specs": {"capacity": "2TB", "interface": "PCIe Gen 4 x4", "formFactor": "M.2 2280"},
            "tags": ["Highly Efficient", "DRAM-less", "Cool Running"]
        }
    ]
}

def scale_database():
    for filename, new_products in NEW_PRODUCTS.items():
        file_path = DATA_DIR / filename
        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Check current products
        existing_products = data.get("products", [])
        existing_names = {p.get("name", "").lower() for p in existing_products}
        
        added = 0
        for new_p in new_products:
            name = new_p.get("name", "")
            if name.lower() not in existing_names:
                existing_products.append(new_p)
                added += 1
                
        # Update product count metadata
        data["productCount"] = len(existing_products)
        data["products"] = existing_products
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        print(f"Updated {filename}: Added {added} products. Total Count: {len(existing_products)}")

if __name__ == '__main__':
    scale_database()
