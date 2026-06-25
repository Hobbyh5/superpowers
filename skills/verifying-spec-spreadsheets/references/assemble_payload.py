"""Assemble the full enrichment payload from all research agents, normalizing the
varied agent JSON into the canonical schema and applying leave-blank discipline:
 - latlong always blank (only city-level was ever found) -> recorded in notes
 - confidence capped at 'medium' (builder pages were 403-blocked everywhere)
 - conflicting HOA -> blank + note
 - 'NOT FOUND' plans -> dropped, noted
"""
import json, copy

BASE = json.load(open("/home/user/superpowers/skills/verifying-spec-spreadsheets/references/example-payload.json"))
payload = copy.deepcopy(BASE)
E = payload["enrichments"]

def web(url):
    return {"value": url, "source": url, "confidence": "medium"}

def cell(value, source, conf="medium"):
    if value in (None, "", "NOT FOUND"):
        return None
    return {"value": value, "source": source, "confidence": conf}

def fp(plan, beds_baths, price, sf, stories, garages, lot, product, source, conf="medium"):
    return {"plan": plan, "unit_type": beds_baths, "base_price": price, "sf": sf,
            "stories": stories, "garages": garages, "lot_width": lot,
            "product": product, "source": source, "confidence": conf}

def add(row, brand, website, delivery, amenities, hoa, plans, notes):
    E[str(row)] = {
        "builder_brand": brand,
        "website": website,
        "delivery": delivery,
        "amenities": amenities,
        "hoa": hoa,
        "floor_plans": [p for p in plans if p],
        "notes": notes,
    }

CO = "coventryhomes.com"

# ---------- HOUSTON (Coventry) ----------
add(130, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/magnolia/escondido-45/"),
    cell("Active", CO),
    cell("Catch-and-release fishing lake, playground, pavilion, exercise equipment, park; nearby Unity Park (trails, wetlands)", CO),
    cell("~$389/mo (median, Maison Property Mgmt)", "tx-hoa.net", "low"),
    [fp("Muenster","3 Bed / 2 Bath",274990,1644,None,None,"45'","Single Family",CO),
     fp("Progreso","4 Bed / 3 Bath",314990,2122,2,None,"45'","Single Family",CO),
     fp("Gunter","4 Bed / 3 Bath",304990,2066,1,None,"45'","Single Family",CO),
     fp("Bloomburg","4 Bed / 3 Bath",334990,2475,2,None,"45'","Single Family",CO),
     fp("Covington","4 Bed / 3 Bath",None,2421,2,2,"45'","Single Family",CO)],
    "Coventry=DFH Texas brand. Magnolia, TX 77354. 'Section 5' not confirmed in public sources. LAT/LONG BLANK (city-level only). Builder site 403; specs from search snippets.")
add(131, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/magnolia/escondido-50/"),
    cell("Active", CO),
    cell("Catch-and-release fishing lake, playground, pavilion, exercise equipment; nearby Unity Park", CO),
    cell("~$389/mo (median, Maison Property Mgmt)", "tx-hoa.net", "low"),
    [fp("Portland","4 Bed / 2 Bath",304990,1677,1,None,"50'","Single Family",CO),
     fp("Kempner","4 Bed / 3 Bath",349990,2493,None,None,"50'","Single Family",CO),
     fp("Justin","4 Bed / 3 Bath",359990,2594,2,None,"50'","Single Family",CO),
     fp("Chappel Hill","4 Bed / 4 Bath",None,2995,None,None,"50'","Single Family",CO)],
    "Magnolia, TX. 'Section 7' not confirmed. LAT/LONG BLANK (city-level only).")
add(132, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/magnolia/escondido-60/"),
    cell("Active", CO),
    cell("Catch-and-release fishing lake, playground, pavilion; nearby Unity Park", CO),
    cell("~$389/mo (median, Maison Property Mgmt)", "tx-hoa.net", "low"),
    [fp("Gordon","4 Bed / 3.5 Bath",434990,3221,1,3,"60'","Single Family",CO),
     fp("Fulshear","4 Bed / 3.5 Bath",None,None,1,None,"60'","Single Family",CO)],
    "Magnolia, TX. 'Section 9' not confirmed. LAT/LONG BLANK (city-level only).")

add(134, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/katy/sofi-lakes/"),
    cell("Coming soon", CO),
    cell("SoFi Mile Park, walking trails, community pool, clubhouse, fitness center", "sofilakes.com"),
    None,
    [fp("Kent","3 Bed / 2.5 Bath",None,None,2,2,"40'","Single Family",CO)],
    "Katy, TX 77493 (Waller Co.). Coming soon; only the Kent plan confirmed for 40', price NOT FOUND. HOA NOT FOUND. LAT/LONG BLANK.")
add(135, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/katy/sofi-lakes/"),
    cell("Coming soon", CO),
    cell("SoFi Mile Park, walking trails, community pool, clubhouse, fitness center", "sofilakes.com"),
    None,
    [],
    "Katy, TX. 50' lineup: plan names/specs/prices NOT FOUND publicly (community ~2,050-4,010 SF range). FLOOR PLANS BLANK. HOA/LAT-LONG BLANK.")

add(136, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/crosby/sundance-cove/"),
    cell("Coming soon", CO),
    cell("Pool, splash pad, amenity center, scenic trails, marina w/ Lake Houston access, playground, fitness center, clubhouse", CO),
    None,
    [],
    "Crosby, TX 77532. Coming soon; Coventry 40' plan names/specs/prices NOT FOUND. HOA conflicting ($62/mo vs $434/mo by section) -> BLANK. LAT/LONG BLANK.")
add(137, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/crosby/sundance-cove/"),
    cell("Coming soon", CO),
    cell("Pool, splash pad, amenity center, scenic trails, marina access, playground, fitness center, clubhouse", CO),
    None,
    [],
    "Crosby, TX. 50' lineup plan names/specs NOT FOUND. HOA conflicting -> BLANK. LAT/LONG BLANK.")

add(138, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/conroe/westridge-cove-40/"),
    cell("Active (selling)", CO),
    cell("Resort-style pool w/ 2-story waterslide, fitness center, playground, greenbelt, recreation complex", CO),
    cell("~$66/mo ($790/yr)", "Jome/HAR", "medium"),
    [fp("Frio","3 Bed / 2 Bath",249990,1400,None,2,"40'","Single Family",CO),
     fp("Gray","3 Bed / 2 Bath",254990,1433,None,2,"40'","Single Family",CO),
     fp("Hill","3 Bed / 2 Bath",264990,1532,None,2,"40'","Single Family",CO),
     fp("Kerr","3 Bed / 2.5 Bath",264990,1647,2,2,"40'","Single Family",CO),
     fp("Kent","3 Bed / 2.5 Bath",269990,1543,2,2,"40'","Single Family",CO),
     fp("King","3 Bed / 2.5 Bath",279990,1792,2,2,"40'","Single Family",CO),
     fp("Lynn","4 Bed / 2.5 Bath",299990,2192,2,2,"40'","Single Family",CO)],
    "Conroe, TX 77304. LAT/LONG BLANK (12048 Moonlight Path Dr; city-level only).")
add(139, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/conroe/westridge-cove-50/"),
    cell("Active (selling)", CO),
    cell("Resort-style pool w/ 2-story waterslide, fitness center, playground, greenbelt, recreation complex", CO),
    cell("~$66/mo ($790/yr)", "Jome/HAR", "medium"),
    [fp("Rains","3 Bed / 2 Bath",269990,1446,1,2,"50'","Single Family",CO),
     fp("Smith","4 Bed / 2 Bath",279990,1596,None,2,"50'","Single Family",CO),
     fp("Starr","4 Bed / 2 Bath",289990,1669,None,2,"50'","Single Family",CO),
     fp("Upton","4 Bed / 3 Bath",309990,1956,None,2,"50'","Single Family",CO),
     fp("Young","4 Bed / 3 Bath",319990,2005,1,2,"50'","Single Family",CO),
     fp("Donley","4 Bed / 2.5 Bath",329990,2209,2,2,"50'","Single Family",CO),
     fp("Martin","4 Bed / 2.5 Bath",334990,2341,None,2,"50'","Single Family",CO),
     fp("Howard","5 Bed / 3.5 Bath",344990,2522,1,2,"50'","Single Family",CO)],
    "Conroe, TX. LAT/LONG BLANK (city-level only).")

add(133, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/dayton/river-ranch-trails/"),
    None,
    cell("Angel Lagoon (40-acre w/ sand beaches), rec center, playground, trails, event lawn, pickleball, dog park", "newhomesmate.com"),
    cell("~$100/mo ($1,200/yr)", "newhomesmate.com", "medium"),
    [fp("Young","Single Family",314990,None,1,2,"50'","Single Family",CO),
     fp("Starr","Single Family",294990,1709,2,2,"50'","Single Family",CO),
     fp("Upton","Single Family",309990,2002,None,3,"50'","Single Family",CO),
     fp("Martin","Single Family",324990,2385,2,None,"50'","Single Family",CO)],
    "Dayton, TX 77535. 'Trails Section 7' not separately confirmed. Beds/baths not captured per plan. Delivery NOT FOUND. LAT/LONG BLANK.")
add(140, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/cove/windcress/"),
    None,
    cell("Resort-style pool, pickleball, putting green, tot lot, playground, scenic trails, recreation center", "WebSearch"),
    cell("~$75/mo ($900/yr)", "texasally.com", "medium"),
    [fp("Rains","Single Family",293990,1446,None,None,"60'","Single Family",CO),
     fp("Smith","Single Family",308990,1596,None,None,"60'","Single Family",CO),
     fp("Starr","Single Family",314990,1669,2,None,"60'","Single Family",CO),
     fp("Upton","Single Family",340989,1956,None,None,"60'","Single Family",CO),
     fp("Donley","Single Family",358990,2209,None,None,"60'","Single Family",CO),
     fp("Martin","Single Family",365990,2341,None,None,"60'","Single Family",CO),
     fp("Howard","Single Family",372990,2522,None,None,"60'","Single Family",CO),
     fp("Young","Single Family",338989,2005,1,2,"60'","Single Family",CO)],
    "Cove, TX 77523 (Mont Belvieu / Barbers Hill ISD). Delivery NOT FOUND. LAT/LONG BLANK.")

# ---------- AUSTIN (Coventry / DFH) ----------
add(38, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/cedar-creek/double-eagle-ranch/"),
    cell("Sold out (quick move-ins only)", "WebSearch"),
    cell("Near McKinney Roughs Nature Park, Bastrop State Park, Lake Bastrop, Lost Pines Golf", "WebSearch"),
    None,
    [fp("Lindale","Single Family",633990,2480,1,2,"1+ acre","Single Family",CO),
     fp("Hamilton","Single Family",656990,2910,1,2,"1+ acre","Single Family",CO),
     fp("Weston","Single Family",714990,3622,2,3,"1+ acre","Single Family",CO)],
    "DISCREPANCY: sheet says 50' Sec 5B / Manor, but the Coventry Double Eagle Ranch is in CEDAR CREEK on 1+ ACRE homesites and is SOLD OUT. Verify this is the same community. LAT/LONG BLANK.")
add(39, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/jarrell/eastern-wells/"),
    None,
    cell("Smart-home pkg, privacy-fenced backyards; I-35 access, Georgetown/Austin proximity", "WebSearch"),
    cell("$33/mo (Coventry section)", "WebSearch", "medium"),
    [fp("Ellis","Single Family",339900,None,2,2,None,"Single Family",CO),
     fp("Howard","Single Family",286900,2533,None,2,None,"Single Family",CO),
     fp("Young","Single Family",344900,2012,1,2,None,"Single Family",CO)],
    "Jarrell, TX (not Austin proper). 'Phase 3' and 50' lot width NOT confirmed. LAT/LONG BLANK.")
add(40, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/georgetown/parmer-ranch-50/"),
    None,
    cell("Fitness center, pool, pickleball, basketball, 10-acre park, zip line, trails, pond", "parmerranch.com"),
    cell("$50/mo", "WebSearch", "medium"),
    [fp("Delta","Single Family",562990,2825,2,None,"50'","Single Family",CO),
     fp("Hideaway","Single Family",627990,2879,1,None,"50'","Single Family",CO)],
    "Georgetown, TX. 'Phases 9 & 10' NOT confirmed. LAT/LONG BLANK.")
add(43, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/tx/taylor/castlewood/"),
    None,
    cell("Clubhouse (fireplace, kitchen), 6+ acres parks", "WebSearch"),
    cell("$35/mo", "WebSearch", "medium"),
    [fp("Hampton","Single Family",289991,1482,1,1,"45'","Single Family","dreamfindershomes.com"),
     fp("Jasper","Single Family",331990,2309,2,2,"45'","Single Family","dreamfindershomes.com")],
    "Taylor, TX. Built by Dream Finders (featured on Coventry site). 45' confirmed. LAT/LONG BLANK.")
add(45, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/tx/taylor/castlewood/"),
    None, None,
    cell("$35/mo", "WebSearch", "low"),
    [],
    "Taylor, TX. Castlewood DUPLEX product not yet released (future phase, expected upper $200s). FLOOR PLANS BLANK - none published. LAT/LONG BLANK.")
add(44, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/georgetown/highland-village-45/"),
    None,
    cell("Playground, nature trails, sports courts, soccer field; Lake Georgetown access", "WebSearch"),
    cell("$75/mo", "WebSearch", "medium"),
    [fp("Troy","Single Family",390990,1992,1,2,"45'","Single Family",CO),
     fp("Izoro","Single Family",370990,1762,1,2,"45'","Single Family",CO)],
    "Georgetown, TX. 12 plans across 45'/50'/55'/60'; Troy & Izoro confirmed for 45'. LAT/LONG BLANK.")

# ---------- DALLAS (Coventry) ----------
add(98, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/heartland/"),
    cell("Active (Apr-May 2026 deliveries cited)", "WebSearch"),
    cell("400+ acres parks, 35-acre lake w/ fishing pier, hike/bike trails, water park, 6 pools, Oasis amenity center", CO),
    cell("$46/mo", "WebSearch", "medium"),
    [fp("Hockley","4 Bed / 2 Bath",324990,1896,1,2,None,"Single Family",CO),
     fp("Kinney","4 Bed / 2 Bath",314990,1723,1,2,None,"Single Family",CO),
     fp("Kimble","3 Bed / 2 Bath",399990,1650,1,2,None,"Single Family",CO),
     fp("Polk","4 Bed / 3 Bath",339900,2123,2,2,None,"Single Family",CO),
     fp("Wilson","4 Bed / 2 Bath",349990,2277,2,2,None,"Single Family",CO),
     fp("Tarrant","4 Bed / 3 Bath",364990,2421,2,2,None,"Single Family",CO)],
    "Heartland, TX (Kaufman Co., ~25 mi E of Dallas; Crandall ISD). 2,100-acre master plan. LAT/LONG BLANK.")
add(99, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/anna/meadow-vista/"),
    None,
    cell("Trails, playgrounds, pool, clubhouse", "WebSearch"),
    None,
    [fp("Kendalia","3 Bed / 2 Bath",351990,1546,None,2,None,"Single Family",CO),
     fp("Grandview","3 Bed / 2 Bath",399990,2041,None,2,None,"Single Family",CO),
     fp("Wimberly","4 Bed / 2 Bath",405990,2076,None,2,None,"Single Family",CO),
     fp("Somerset","4 Bed / 3 Bath",454990,2305,None,2,None,"Single Family",CO)],
    "Anna, TX (N. Dallas; Anna ISD). Delivery NOT FOUND. HOA for Coventry section NOT FOUND -> BLANK. LAT/LONG BLANK.")

# ---------- SAN ANTONIO (Coventry) ----------
add(207, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/schertz/rhine-valley/"),
    None,
    cell("Rhine Valley Park, soccer fields, running trails, basketball courts", CO),
    cell("~$35/mo ($420/yr)", "tx-hoa.net", "medium"),
    [fp("Gaines","Single Family",435445,2123,1,2,None,"Single Family",CO),
     fp("Wingate","Single Family",None,None,2,None,None,"Single Family",CO,"low")],
    "Schertz, TX (NE San Antonio) — note sheet implied New Braunfels. Lot widths not confirmed. LAT/LONG BLANK.")
add(208, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/san-antonio/garden-grove/"),
    None,
    cell("Planned amenity center w/ pool, pavilion", CO),
    cell("~$40/mo ($480/yr)", "WebSearch", "medium"),
    [fp("Hill","Single Family",269990,1532,None,2,"40'","Single Family",CO),
     fp("Young","Single Family",None,None,None,2,"50'","Single Family",CO,"low")],
    "San Antonio, TX. 40' and 50' sections. Range 1,433-2,522 SF, $255,990-$379,690. LAT/LONG BLANK.")
add(209, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/schertz/the-parklands/"),
    None,
    cell("Hiking/biking trails, pavilion, playgrounds, sport courts, community pool", "homes.com"),
    cell("~$44/mo ($532/yr)", "WebSearch", "medium"),
    [fp("Somerset","Single Family",419990,2358,None,2,"60'","Single Family",CO)],
    "Schertz, TX (near Santa Clara). 50' and 60' lots; only a 60' plan (Somerset) captured. Sheet says 50's — 50' plan names NOT captured. LAT/LONG BLANK.")
add(210, "Coventry Homes",
    web("https://www.coventryhomes.com/new-homes/tx/san-antonio/stillwater-ranch/"),
    None,
    cell("6,000 SF resort pool w/ beach entry, kiddie pool, fitness room, basketball, tennis, playgrounds; nearby Government Canyon trails", CO),
    None,
    [fp("Woodlake","Single Family",444990,2579,2,None,"45'","Single Family",CO)],
    "San Antonio, TX. Multi-builder. 45' and 60' lots; one 45' plan (Woodlake) captured. HOA conflicting ($60/mo vs $342 semi-annual) -> BLANK. LAT/LONG BLANK.")

# ---------- COLORADO (DFH) ----------
DF = "dreamfindershomes.com"
add(93, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/co/windsor/trevenna/"),
    None,
    cell("Parks, trails, lake access; recreation center nearby", DF, "low"),
    None,
    [fp("Silverthorne","Single Family",499990,1895,1,3,None,"Single Family",DF),
     fp("Rainier","Single Family",524990,2253,2,3,None,"Single Family",DF),
     fp("Willow","Single Family",564990,2448,2,2,None,"Single Family",DF),
     fp("Antero","Single Family",509990,2145,2,2,None,"Single Family",DF),
     fp("Sierra","Single Family",539990,2476,2,None,None,"Single Family",DF)],
    "Windsor, CO 80550. Front garages, all-electric, no basements. HOA/delivery NOT FOUND. LAT/LONG BLANK.")
add(94, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/co/bennett/muegge-farms/"),
    None,
    cell("Pocket parks, community center, greenbelts", DF, "low"),
    cell("~$100/mo ($1,200/yr)", "WebSearch", "medium"),
    [fp("Silverthorne","Single Family",464990,1894,1,2,None,"Single Family",DF),
     fp("Rainier","Single Family",489990,2253,2,2,None,"Single Family",DF),
     fp("Willow","Single Family",509990,2448,2,2,None,"Single Family",DF),
     fp("Antero","Single Family",469990,2131,2,2,None,"Single Family",DF)],
    "Bennett, CO (Bennett SD). Multi-builder master plan. Delivery NOT FOUND. LAT/LONG BLANK.")
add(95, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/co/berthoud/farmstead/"),
    None,
    cell("Community pool, splash pad, trails, future elementary school; non-potable irrigation", DF),
    None,
    [fp("Alpine","Single Family",509990,1700,1,None,None,"Single Family",DF),
     fp("Silverthorne","Single Family",524990,1895,1,2,None,"Single Family",DF),
     fp("Antero","Single Family",529990,2131,2,2,None,"Single Family",DF),
     fp("Rainier","Single Family",539990,2253,2,2,None,"Single Family",DF),
     fp("Sierra","Single Family",584990,2476,2,None,None,"Single Family",DF),
     fp("Willow","Single Family",584990,2448,2,2,None,"Single Family",DF),
     fp("Denali","Single Family",599990,2600,2,3,None,"Single Family",DF),
     fp("Conifer","Single Family",614990,2944,2,None,None,"Single Family",DF)],
    "Berthoud, CO 80513 (no metro district). 50' and 60' lots. Sheet says '50s'. HOA NOT FOUND. LAT/LONG BLANK.")
add(96, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/co/broomfield/parkside-west-at-baseline/"),
    None,
    cell("Neighborhood parks, gardenways, trails, amphitheater, pool, golf simulator", DF),
    cell("$79/mo", DF, "medium"),
    [fp("Beacon","Townhome",584990,2002,4,2,None,"Townhome",DF),
     fp("Overlook","Townhome",513990,1667,3,2,None,"Townhome",DF)],
    "Broomfield, CO 80023 (Baseline master plan). Parkside West II & III — TOWNHOMES only. LAT/LONG BLANK.")
add(97, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/co/frederick/hidden-creek/"),
    None,
    cell("2 neighborhood parks, trails, playgrounds, open space", DF),
    cell("$50/mo ($600/yr)", "WebSearch", "medium"),
    [fp("Silverthorne","Single Family",516990,1894,1,2,None,"Single Family",DF),
     fp("Newport","Single Family",521990,1887,1,None,None,"Single Family",DF),
     fp("Antero","Single Family",536990,2145,2,2,None,"Single Family",DF),
     fp("Rainier","Single Family",546990,2253,2,2,None,"Single Family",DF),
     fp("Sierra","Single Family",566990,2476,2,None,None,"Single Family",DF),
     fp("Conifer","Single Family",606990,2944,2,None,None,"Single Family",DF)],
    "Frederick, CO 80530 ('Hidden Creek North'; LGI also builds a different Hidden Creek). Delivery NOT FOUND. LAT/LONG BLANK.")

# ---------- PHOENIX (DFH) ----------
add(198, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/az/san-tan-valley/bella-vista-farms/"),
    cell("Pre-launch (sales expected 2025-26)", "WebSearch", "low"),
    cell("11-acre park, pool, splash pad, basketball, soccer field, shaded ramadas", "WebSearch"),
    cell("$95/mo", "WebSearch", "medium"),
    [],
    "San Tan Valley, AZ. DFH acquired 122 50' lots (Phase 4). Multi-builder master plan. DFH plan names/specs NOT FOUND (community 1,895-2,900 SF, from ~$341,990) -> FLOOR PLANS BLANK. LAT/LONG BLANK.")
add(200, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/az/maricopa/rancho-mirage/"),
    cell("Selling (opened Mar 2025)", "phoenixagentmagazine.com"),
    cell("Pickleball, playground, lake w/ fishing, basketball court", "WebSearch"),
    cell("~$104/mo", "Jome", "medium"),
    [fp("Daffodil II","3 Bed / 2 Bath",297990,1593,None,None,None,"Single Family",DF),
     fp("Goldenrod II","4 Bed / 2 Bath",329990,1705,None,None,None,"Single Family",DF),
     fp("Passionflower II","4 Bed / 3 Bath",334990,1968,None,None,None,"Single Family",DF)],
    "Maricopa, AZ. Range $297,990-$437,990. Water Lily II plan exists but specs NOT FOUND. LAT/LONG BLANK.")
add(201, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/az/san-tan-valley/skyline-village/"),
    cell("Coming soon", "WebSearch", "low"),
    cell("Planned: park, clubhouse, gym, pool, trails, dog park, tennis, pickleball, bocce, volleyball, basketball (community center opens 2026)", "WebSearch"),
    None,
    [],
    "San Tan Valley, AZ. DFH has 129 lots in 300-acre Skyline Village. From ~$380,000. DFH plan names/specs NOT FOUND -> FLOOR PLANS BLANK. HOA NOT FOUND. LAT/LONG BLANK.")
add(202, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/az/buckeye/apache-farms/"),
    cell("Selling (Grand Opening Feb 2026)", "WebSearch"),
    cell("Parks, walking trails, half-court basketball, playgrounds, open spaces", "WebSearch"),
    None,
    [fp("Alamo","3 Bed / 2 Bath",364990,1556,1,2,None,"Single Family",DF),
     fp("Corona","Single Family",379990,1750,None,None,None,"Single Family",DF),
     fp("Havasu","4 Bed / 2 Bath",400990,1958,None,None,None,"Single Family",DF),
     fp("Horizon","4 Bed / 3 Bath",409990,2179,None,3,None,"Single Family",DF),
     fp("Pleasant","4 Bed / 3 Bath",430990,2378,None,None,None,"Single Family",DF)],
    "Buckeye, AZ (85 homesites). Range $364,990-$489,845. Helios plan exists but specs NOT FOUND. HOA NOT FOUND. LAT/LONG BLANK.")

# ---------- MYRTLE BEACH + NASHVILLE (DFH) ----------
add(174, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/nc/calabash/calabash-palms/"),
    None,
    cell("2 scenic ponds, dog park; maintenance-free", DF),
    cell("$180/mo (incl. lawn/grounds)", "WebSearch", "medium"),
    [fp("Cameron","Townhome",240000,1704,2,1,None,"Townhome",DF),
     fp("Filmore","Townhome",246990,1736,2,1,None,"Townhome",DF)],
    "Calabash, NC. Maintenance-free townhomes (3-4 bed), $227K-$264K. LAT/LONG BLANK.")
add(175, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/nc/ocean-isle/villas-at-seaside/"),
    cell("Sold out (new phase coming)", "WebSearch", "low"),
    cell("4 mi to beach; 10+ golf courses within 10 min; lawn care & exterior insurance incl.", DF),
    None,
    [fp("Wylie","Townhome",282000,1566,2,2,None,"Townhome",DF),
     fp("Glenville","Townhome",288000,1731,2,2,None,"Townhome",DF),
     fp("Wisteria","Townhome",309990,1969,2,2,None,"Townhome",DF),
     fp("Ivy","Villa",None,1604,1,2,None,"Villa",DF)],
    "Ocean Isle Beach, NC. Townhomes & villas. Sold out as of Jun 2026. HOA NOT FOUND. LAT/LONG BLANK.")
add(176, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/tn/smyrna/briley-downs/"),
    cell("Active (10+ move-in ready)", "WebSearch"),
    cell("Resort-style pool, playground, dog park, walking trails", DF),
    cell("$90/mo", "nashvillehome.guru", "medium"),
    [fp("Aspen","Single Family",452990,1713,None,2,None,"Single Family",DF),
     fp("Hadley","Single Family",443990,2003,None,2,None,"Single Family",DF),
     fp("Beaufain","Single Family",462990,2310,None,2,None,"Single Family",DF),
     fp("Windermere","Single Family",477990,2459,None,2,None,"Single Family",DF),
     fp("Tellico","Single Family",532990,2793,None,2,None,"Single Family",DF),
     fp("Bellwood","Single Family",509990,2494,None,2,None,"Single Family",DF),
     fp("Ironwood","Single Family",518990,2919,None,2,None,"Single Family",DF)],
    "Smyrna, TN (not Nashville proper). 3-5 bed, $444K-$615K. Sheet says '45''. LAT/LONG BLANK.")
add(177, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/tn/white-bluff/maple-crest/"),
    cell("Coming soon", "Zillow", "low"),
    cell("Playground, open green spaces; near Montgomery Bell State Park", "Zillow"),
    None,
    [],
    "White Bluff, TN. From ~$299,900 (low $300s), 2-4 bed. Plan names NOT FOUND -> FLOOR PLANS BLANK. HOA NOT FOUND. LAT/LONG BLANK.")

# ---------- MISC EAST (DFH) ----------
add(33, "Dream Finders Homes", None, None, None, None, [],
    "NOT FOUND — no DFH 'Village Towns' community confirmable in the Atlanta division (note: a 'Villages at Harris Creek', West Point GA, is separate and already in the sheet). Needs internal/sales confirmation. ALL FIELDS BLANK.")
add(46, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/md/waldorf/spring-haven/"),
    None,
    cell("Parks, tot lots, walking paths, green spaces", DF),
    None,
    [fp("Norbury","Townhome",414990,None,3,1,None,"Townhome",DF),
     fp("Brexton","Townhome",429990,2095,3,2,None,"Townhome",DF),
     fp("Dalton","Single Family",609990,3053,2,2,None,"Single Family",DF),
     fp("Oakley","Single Family",644990,3638,2,2,None,"Single Family",DF),
     fp("Stirling","Single Family",689990,3839,2,2,None,"Single Family",DF)],
    "Capital division = Waldorf, MD (Charles Co., metro DC). TH ($415K-$430K) + SFD ($610K-$690K). HOA NOT FOUND. LAT/LONG BLANK.")
add(60, "Dream Finders Homes",
    web("https://dreamfindershomes.com/new-homes/nc/matthews/arbor-village/"),
    cell("Active (final opportunities)", "Redfin", "low"),
    cell("Studio-above-garage option on select homesites", DF, "low"),
    None,
    [fp("Red Oak","Single Family",447900,1781,2,2,None,"Single Family",DF),
     fp("Amberlea","Single Family",514900,2415,None,None,None,"Single Family",DF)],
    "Charlotte division = Matthews, NC 28105. Range $447,900-$524,900; final opportunities. HOA NOT FOUND. LAT/LONG BLANK.")
add(113, "Dream Finders Homes", None, None, None, None, [],
    "NOT FOUND — no DFH 'East River' community confirmable in the Greenville SC division. DFH does build in Greenville/Spartanburg/Anderson, but this name wasn't found. Needs internal/sales confirmation. ALL FIELDS BLANK.")

json.dump(payload, open("/tmp/claude-0/-home-user-superpowers/214c8f3f-1c1b-5372-ab5f-5f561af395cf/scratchpad/payload_full.json","w"), indent=1)
print("enrichments now:", len(payload["enrichments"]))
print("rows:", sorted(int(k) for k in payload["enrichments"]))
