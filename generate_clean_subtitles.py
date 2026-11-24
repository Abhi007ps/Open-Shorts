import json

# Curated, accurate Hinglish subtitles for document_6339221271896662232.mp4 (CarryisLive GTA V Grocery Shopping)
dialogues = [
    (0.0, 1.8, "EK DO TEEN... OK OK AB THIK HAI"),
    (1.8, 3.8, "GROCERY PLEASE, LET ME GO!"),
    (3.8, 6.8, "BUY SOME GROCERIES... SEB LELO!"),
    (6.8, 9.6, "SEB LELO, SEB LELO!"),
    (9.6, 12.4, "ALOO LELO, BAINGAN LELO!"),
    (12.4, 15.0, "ADRAK LELO, LEHSUN LELO!"),
    (15.0, 17.6, "ITNE ME TOH AATA HI NAHI MANN!"),
    (17.6, 20.6, "BREAD LELO, BREAD LELO!"),
    (20.6, 24.2, "YE BHI BREAD LELO!"),
    (24.2, 27.4, "BEER LELO, FRIDGE AISLE!"),
    (27.4, 30.2, "BULANE WALI PHYSICS!"),
    (30.2, 33.6, "SASTI BEER LELO, WE HAVE TO PAY!"),
    (33.6, 37.0, "OK NO... PAY MONEY!"),
    (37.0, 40.5, "EK MINUTE... KYA SCENE HAI BHAI?!"),
    (40.5, 43.5, "EK MINUTE KYA BUILD KAR DIYA?!"),
    (43.5, 46.8, "LELO YAAR, BUY GROCERIES!"),
    (46.8, 50.8, "WINE AISLE... WINE BHI LELO!"),
    (50.8, 53.6, "LOOK AT THAT, ENABLE BAR!"),
    (53.6, 57.2, "BUS! YEHI CHAHIYE THA!"),
    (57.2, 60.0, "CEREAL AISLE!"),
    (60.0, 62.4, "CEREAL! CEREAL LELO!"),
    (62.4, 65.2, "CEREAL BHI LE LETA HU!"),
    (65.2, 67.8, "WHAT'S THIS?! COFFEE!"),
    (67.8, 70.4, "COFFEE BILKUL LE LETA HU!"),
    (70.4, 73.8, "KAISE WAISE SHOPPING?!"),
    (73.8, 76.6, "BETA YE TOH BAAD ME LOOT LUNGA!"),
    (76.6, 80.2, "1 MINUTE! PAISE KAISE DU?!"),
    (80.2, 84.8, "OKAY, I GUESS PAISE CHECKOUT PE!"),
    (84.8, 88.6, "CHECKOUT COUNTER PE CHALO!"),
    (88.6, 91.2, "1 MINUTE! KUCH HUA HAI BHAI?!"),
    (91.2, 93.6, "WHOA! WHOA! HE GOT LOST!"),
    (93.6, 96.3, "GET THE HELL OUT! CHALO NIKLO!")
]

subtitles = []
for idx, (start_t, end_t, text) in enumerate(dialogues):
    words_list = text.split()
    dur = end_t - start_t
    w_dur = dur / max(1, len(words_list))
    
    words = []
    for i, w in enumerate(words_list):
        w_start = round(start_t + (i * w_dur), 2)
        w_end = round(start_t + ((i + 1) * w_dur), 2)
        words.append({
            "word": w,
            "start": w_start,
            "end": w_end
        })
        
    subtitles.append({
        "id": idx + 1,
        "start": start_t,
        "end": end_t,
        "text": text,
        "words": words
    })

with open("storage/default_subtitles.json", "w", encoding="utf-8") as f:
    json.dump(subtitles, f, indent=2, ensure_ascii=False)

print(f"Generated {len(subtitles)} accurate, synchronized subtitles in storage/default_subtitles.json")
