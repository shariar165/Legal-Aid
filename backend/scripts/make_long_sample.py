"""Write demo/docs/long_migrant_msa.txt: a long (~25 page) FICTIONAL manpower-supply agreement for the long-context test.

    python -m scripts.make_long_sample

Everything here is invented: no real company, person or address. The risky terms of the hero contracts are scattered
through ordinary boilerplate (definitions, numbered sub-clauses, schedules and rate tables), and one trap only shows
when two far-apart parts are read together: the passport deposit in Part 3 and the "absconding" penalty in Schedule 4.
The file is deterministic, so the test and the eval always read the same text.
"""

from __future__ import annotations

from ain import config

OUT = config.DEMO_DIR / "docs" / "long_migrant_msa.txt"

TRADES = [
    "General Labourer", "Mason", "Steel Fixer", "Carpenter (Shuttering)", "Plumber", "Electrician", "Pipe Fitter", "Welder (Arc)",
    "Welder (TIG)", "Painter", "Tile Setter", "Scaffolder", "Rigger", "Crane Signalman", "Forklift Operator", "Light Vehicle Driver",
    "Heavy Vehicle Driver", "HVAC Technician", "Cleaner (Facilities)", "Cleaner (Hospital)", "Kitchen Helper", "Cook", "Laundry Attendant",
    "Gardener", "Pool Attendant", "Security Guard", "Store Keeper", "Messenger", "Office Boy", "Car Washer", "Glazier", "Insulator",
    "Duct Fabricator", "Mechanic (Light)", "Mechanic (Heavy)", "Auto Electrician", "Tyre Fitter", "Surveyor Helper", "Lab Helper",
    "Waste Handler", "Pest Control Operator", "Maintenance Technician", "Lift Technician Helper", "Fire Watch", "Housekeeper",
]
REGIONS = ["Riyadh region", "Eastern Province", "Qassim and Hail"]
CITIES = ["Riyadh", "Al Kharj", "Diriyah", "Dammam", "Al Khobar", "Jubail", "Hofuf", "Buraydah", "Unaizah", "Hail"]
PPE = [
    "safety helmet (class E)", "safety shoes (steel toe)", "high-visibility vest", "safety goggles", "face shield", "ear plugs",
    "ear muffs", "dust mask (FFP2)", "chemical respirator", "leather gloves", "rubber gloves", "cut-resistant gloves", "welding gloves",
    "welding apron", "full-body harness", "lanyard with shock absorber", "coverall (summer)", "coverall (winter)", "rain coat",
    "sun hood", "cooling towel", "knee pads", "first-aid pouch", "water bottle (1.5 L)", "headlamp",
]
COURSES = [
    "Induction and site rules", "Working in heat", "Working at height", "Scaffold inspection", "Manual handling", "Fire safety and evacuation",
    "First aid basics", "Electrical safety", "Hot work permits", "Confined space awareness", "Chemical handling (SDS)", "Hand and power tools",
    "Excavation safety", "Lifting operations", "Traffic management on site", "Housekeeping", "Hygiene in camps", "Reporting incidents",
    "Cultural orientation", "Grievance channels", "Basic Arabic phrases", "Road safety for drivers",
]

DEFINITIONS = [
    ("Agreement", "this Manpower Supply and Employment Agreement, its Parts, Schedules and any written amendment signed by both Parties"),
    ("Agency", "the recruiting agency named in the preamble, licensed in Bangladesh to recruit workers for overseas employment"),
    ("Company", "the employer named in the preamble, a facilities and construction services company in the Kingdom of Saudi Arabia"),
    ("Worker", "each person recruited by the Agency and employed by the Company under this Agreement, as listed in the Mobilisation Schedule"),
    ("Mobilisation Schedule", "the list of selected Workers, their trades and arrival dates issued under clause 2.5"),
    ("Site", "any project, facility or premises listed in Schedule 2 or later notified by the Company"),
    ("Camp", "the accommodation provided or arranged by the Company for Workers"),
    ("Basic Salary", "the fixed monthly amount stated for the Worker's trade in Schedule 1, excluding allowances and overtime"),
    ("Allowances", "any food, transport or other allowance stated in Schedule 1 or in a written notice of the Company"),
    ("Overtime", "hours worked beyond the normal hours stated in clause 5.1"),
    ("Iqama", "the residence permit issued to a non-Saudi worker in the Kingdom"),
    ("Work Permit", "the permit allowing the Worker to work for the Company in the Kingdom"),
    ("Probation Period", "the first ninety (90) days after the Worker's arrival"),
    ("Contract Term", "two (2) years from the Worker's date of arrival in the Kingdom, unless ended earlier under Part 9"),
    ("Recruitment Costs", "all fees, charges and expenses of selection, documentation, visa, medical examination, training and travel to the Kingdom"),
    ("Supervisor", "the person appointed by the Company to direct the Worker's daily work at a Site"),
    ("Disciplinary Code", "the code of conduct and penalties set out in Schedule 4"),
    ("Grievance", "any complaint by a Worker about pay, conditions, treatment or safety"),
    ("Force Majeure Event", "an event beyond the reasonable control of a Party, including war, epidemic, flood and government action"),
    ("Business Day", "a day other than a Friday, Saturday or official holiday in the Kingdom"),
    ("Confidential Information", "all non-public information about a Party, its clients, prices, methods and personnel"),
    ("Replacement Worker", "a worker supplied by the Agency in place of a Worker who leaves during the Probation Period"),
    ("Service Fee", "the fee payable by the Company to the Agency for each Worker supplied, as stated in clause 2.9"),
    ("PPE", "the personal protective equipment listed in Schedule 3"),
    ("Training Plan", "the courses listed in Schedule 7"),
    ("Accommodation Standards", "the minimum standards for the Camp set out in Schedule 5"),
    ("Kingdom", "the Kingdom of Saudi Arabia"),
    ("Parties", "the Agency and the Company, and where the context requires, the Worker"),
]

GENERAL = [
    ("Notices", "Any notice under this Agreement shall be in writing in English and delivered by hand, courier or email to the address of the receiving Party stated in the preamble, and is deemed received on the next Business Day after sending."),
    ("Assignment", "Neither the Agency nor the Company may assign or transfer its rights or obligations under this Agreement without the prior written consent of the other Party, which shall not be unreasonably withheld."),
    ("Subcontracting", "The Company may assign Workers to work at Sites of its clients, provided the Company remains the employer and remains responsible for all payments due to the Workers."),
    ("Entire Agreement", "This Agreement, its Parts and Schedules constitute the entire agreement between the Parties on its subject and supersede all prior negotiations, representations and understandings."),
    ("Amendment", "No amendment of this Agreement is effective unless it is in writing and signed by authorised representatives of the Agency and the Company."),
    ("Severability", "If any provision of this Agreement is held invalid or unenforceable, the remaining provisions remain in full force, and the invalid provision shall be replaced by a valid provision closest to its intent."),
    ("Waiver", "A failure or delay by a Party to exercise any right under this Agreement is not a waiver of that right, and a single or partial exercise does not prevent any further exercise."),
    ("Counterparts", "This Agreement may be signed in any number of counterparts, each of which is an original and all of which together form one instrument."),
    ("Confidentiality", "Each Party shall keep the Confidential Information of the other Party confidential and use it only to perform this Agreement, during the Contract Term and for three (3) years afterwards."),
    ("Anti-Bribery", "Neither Party shall offer, give, request or accept any bribe, facilitation payment or improper advantage in connection with this Agreement."),
    ("Insurance", "The Company shall maintain public liability insurance for its Sites and motor insurance for vehicles used to transport Workers."),
    ("Audit", "The Company may, on reasonable notice, inspect the Agency's records relating to the selection and documentation of the Workers supplied under this Agreement."),
    ("Records", "The Company shall keep payroll and attendance records for each Worker for the Contract Term and two (2) years afterwards."),
    ("Language", "This Agreement is made in English. Any translation is for convenience only and the English text prevails."),
    ("Costs", "Each Party bears its own costs of negotiating and signing this Agreement."),
    ("Relationship", "Nothing in this Agreement creates a partnership or agency relationship between the Agency and the Company, except as required by the law applicable to the recruitment of the Workers."),
    ("Further Assurance", "Each Party shall sign such further documents and do such further acts as may reasonably be required to give effect to this Agreement."),
    ("Data", "The Company may keep copies of the Workers' identity documents, photographs and medical reports for employment purposes and to comply with the law of the Kingdom."),
    ("Announcements", "Neither Party shall make any public announcement about this Agreement without the written approval of the other Party."),
    ("Survival", "Clauses 9.6, 10.1, 11.1 to 11.4 and 12.9 survive the termination or expiry of this Agreement."),
]

HSE = [
    "The Company shall provide each Worker with the PPE listed in Schedule 3 free of charge and replace worn or damaged items promptly.",
    "The Worker shall wear the PPE required for each task and shall not remove or tamper with any guard or safety device.",
    "No work in direct sunlight shall be carried out between 12:00 and 15:00 from 15 June to 15 September, in line with the midday work ban of the Kingdom.",
    "The Company shall provide cool drinking water, shaded rest areas and electrolyte drinks at every Site.",
    "A Worker who feels unwell from heat shall stop work and report to the Supervisor, and shall not be penalised for doing so.",
    "Work at height above two (2) metres requires a permit, a trained Worker and a full-body harness attached to a certified anchor point.",
    "Scaffolds shall be erected, altered and dismantled only by trained scaffolders and inspected before each shift.",
    "Hot work requires a permit, a fire watch and a fire extinguisher within reach for the whole duration of the work.",
    "Entry into a confined space requires a permit, gas testing and a standby attendant outside the space.",
    "Electrical work shall be done only by qualified electricians under a lock-out and tag-out procedure.",
    "Every incident, near miss and injury shall be reported to the Supervisor on the same shift and recorded by the Company.",
    "The Company shall provide first aid at every Site and transport an injured Worker to a clinic or hospital without delay and at its own cost.",
    "Workers shall attend the courses of the Training Plan in Schedule 7 during working hours.",
    "Vehicles used to transport Workers shall have a seat for each passenger, air conditioning and a valid inspection certificate.",
    "Smoking is not allowed at any Site except in marked areas away from flammable materials.",
    "Chemicals shall be stored in labelled containers and used only with the safety data sheet available at the place of use.",
    "Excavations deeper than one point two (1.2) metres shall be shored, sloped or benched before any Worker enters.",
    "Lifting operations shall follow a lift plan, and no Worker shall stand under a suspended load.",
    "The Company shall carry out a safety inspection of each Site at least weekly and keep the report for two (2) years.",
    "A Worker may refuse work that he reasonably believes presents a serious and imminent danger to his life or health.",
]


SITE_RULES = [
    "Report to the Supervisor at the start of every shift and sign the attendance sheet.",
    "Keep walkways, stairs and exits clear of materials and waste.",
    "Do not operate any machine, vehicle or tool you have not been trained and authorised to use.",
    "Do not enter areas marked with a red barrier tape unless you hold the permit for that area.",
    "Use only the toilets and washing facilities provided at the Site.",
    "Eat and drink only in the rest areas, never at the work face.",
    "Report any damaged tool, cable or ladder at once and do not use it.",
    "Do not bring visitors to the Site without the site manager's approval.",
    "Do not take photographs at a client's Site unless the client allows it.",
    "Mobile phones may be used only in the rest areas, except by Supervisors and drivers in an emergency.",
    "Follow the instructions of the fire wardens during drills and emergencies.",
    "Keep your Site pass visible at all times.",
    "Store tools in the Site store at the end of each shift.",
    "Do not remove any material from the Site without a gate pass.",
    "Report any spill of oil, fuel or chemicals to the Supervisor immediately.",
    "Respect the privacy of patients, students and residents at client Sites.",
    "Do not enter client offices or homes unless your task requires it.",
    "Speak politely to clients and members of the public and refer any complaint to the Supervisor.",
    "Keep noise to a minimum near hospitals, schools and homes.",
    "Wash your hands before meals and after handling waste or chemicals.",
    "Report any harassment or abuse to the Supervisor or through the grievance contacts in the Camp.",
    "Take the breaks shown on the Site notice board, including the hydration breaks in summer.",
    "Do not work alone in remote parts of a Site; keep a colleague within sight.",
    "Follow the speed limits and one-way routes for vehicles on the Site.",
    "Leave the Site only through the main gate and sign out at the end of the shift.",
]
CAMP_RULES = [
    "Lights out at 23:00 on working days, except in the recreation room.",
    "Cooking is allowed only in the kitchen or canteen, never in rooms.",
    "Keep rooms clean; inspections take place weekly.",
    "Visitors from outside the Camp are allowed only in the reception area.",
    "Do not use electric heaters or hot plates in rooms.",
    "Report any fault in air conditioning, water or electricity to the camp boss.",
    "Keep valuables in your lockable cupboard; the Company is not liable for unlocked items.",
    "Gambling and the sale of goods in the Camp are not allowed.",
    "Respect the prayer times and the prayer area.",
    "Do not move furniture between rooms without the camp boss's approval.",
    "Waste must be placed in the bins provided and sorted where marked.",
    "Use the laundry on the days set for your block.",
    "Television in the recreation room is switched off at 23:00.",
    "Fire exits must never be locked or blocked.",
    "Smoking is allowed only in the marked outdoor area.",
    "Pets are not allowed in the Camp.",
    "Report any illness in your room so that the first-aider can check on it.",
    "The camp boss may enter rooms for inspection with one other Worker present.",
]
KPIS = [
    ("Demand letter to arrival", "average days from demand letter to arrival of a batch", "90 days", "SAR 100 per Worker per week late"),
    ("Trade test pass rate", "share of Workers confirmed in their trade after probation", "90%", "free Replacement Worker for each failure"),
    ("Medical fitness", "share of Workers fit at the medical test in the Kingdom", "98%", "Agency refunds the Service Fee for each unfit Worker"),
    ("Document accuracy", "visas and documents issued without error", "99%", "Agency pays the cost of correction"),
    ("Orientation attendance", "share of Workers who attended pre-departure orientation", "100%", "written warning"),
    ("Replacement time", "days to supply a Replacement Worker", "60 days", "SAR 50 per day late"),
    ("Complaint response", "days for the Agency to answer a Company complaint", "5 Business Days", "written warning"),
    ("Report delivery", "monthly recruitment report delivered on time", "100%", "written warning"),
    ("Trade mix", "batches matching the trades in the demand letter", "95%", "Company may reject the batch"),
    ("Language skills", "Workers able to follow basic instructions in English or Arabic", "80%", "extra language training at the Agency's cost"),
    ("Driving licences", "drivers holding a licence valid for conversion in the Kingdom", "100%", "Agency refunds the Service Fee"),
    ("Attrition in probation", "Workers leaving during the Probation Period", "below 5%", "free Replacement Worker"),
    ("Compliance with law", "batches recruited with every permission required in Bangladesh", "100%", "Company may terminate this Agreement"),
    ("Data accuracy", "Mobilisation Schedules without errors", "98%", "Agency corrects within 2 Business Days"),
    ("Record keeping", "files complete at audit", "100%", "written warning"),
    ("Health checks", "Workers with complete vaccination records", "100%", "Agency arranges vaccination at its own cost"),
    ("Pre-departure briefing on contract", "Workers given a copy of their terms before departure", "100%", "written warning"),
    ("Escalations", "complaints escalated to senior management", "below 2 per quarter", "quarterly review meeting"),
]


def _site_rules() -> str:
    rows = ["SCHEDULE 8 - SITE RULES", ""]
    rows += [f"8.{i} {t}" for i, t in enumerate(SITE_RULES, 1)]
    return "\n".join(rows)


def _kpis() -> str:
    rows = ["SCHEDULE 9 - AGENCY SERVICE LEVELS", "", "Measure | Definition | Target | Consequence if missed"]
    rows += [" | ".join(k) for k in KPIS]
    rows.append("")
    rows.append("Service levels are reviewed every quarter. A consequence applies only after the Company has notified the Agency in writing and given it ten (10) Business Days to explain.")
    return "\n".join(rows)


def _pay_examples() -> str:
    rows = ["SCHEDULE 10 - WORKED PAY EXAMPLES", "", "The examples below show how monthly pay is computed for a Worker with 26 working days and the overtime shown. They are illustrations only."]
    for g in range(1, 10):
        basic = 1000 + (0 if g < 5 else 50 * (g - 4))
        food = 200 + 25 * (g % 3)
        ot_hours = 10 + 4 * g
        ot = round(basic / 240 * 1.5 * ot_hours, 2)
        rows.append("")
        rows.append(f"Example {g} (grade G-{g:02d}): Basic Salary SAR {basic:,}; food allowance SAR {food}; overtime {ot_hours} hours at SAR {round(basic / 240 * 1.5, 2)} = SAR {ot:,}.")
        rows.append(f"Gross pay SAR {basic + food + ot:,.2f}. Deductions under clause 4.4 in the first year: SAR 650. Net pay SAR {basic + food + ot - 650:,.2f}.")
        rows.append("If the Worker was absent without notice for one day, one day's Basic Salary is also deducted under Schedule 4.")
    return "\n".join(rows)


def _camp_rules() -> str:
    rows = ["SCHEDULE 11 - CAMP RULES", ""]
    rows += [f"11.{i} {t}" for i, t in enumerate(CAMP_RULES, 1)]
    return "\n".join(rows)


def _annex_terms() -> str:
    return "\n".join([
        "ANNEX A - INDIVIDUAL EMPLOYMENT TERMS",
        "",
        "A.1 Each Worker's individual terms are those of this Agreement for his trade, as listed in the Mobilisation Schedule: position, Site, Basic Salary from Schedule 1, Allowances, normal hours, leave and the Contract Term.",
        "A.2 The Agency shall read the individual terms to each Worker before departure and record that it has done so.",
        "A.3 If an individual term differs from this Agreement, the term more favourable to the Worker applies.",
        "A.4 The individual terms are signed by the Worker, the Agency and the Company in three originals.",
        "",
        "১. কর্মী এই চুক্তির সকল শর্ত পড়িয়া ও বুঝিয়া স্বেচ্ছায় স্বাক্ষর করিলেন।",
    ])


DUTIES = [
    "prepares the work area, moves materials by hand or trolley and keeps the area clean",
    "reads simple drawings, sets out lines and levels and builds to the tolerances given by the Supervisor",
    "checks tools and equipment before use and reports defects",
    "follows the method statement and the permit conditions for the task",
    "records the quantities completed on the daily sheet",
    "works with other trades to keep the sequence of work and avoid clashes",
]


def _job_descriptions() -> str:
    rows = ["SCHEDULE 12 - JOB DESCRIPTIONS", ""]
    for i, trade in enumerate(TRADES, 1):
        a, b, c = DUTIES[i % 6], DUTIES[(i + 2) % 6], DUTIES[(i + 4) % 6]
        rows.append(
            f"12.{i} {trade}. Reports to the Supervisor of the Site. The {trade.lower()} {a}; {b}; and {c}. "
            f"Minimum experience: {1 + i % 4} year(s) in the trade. Trade test: {'practical and oral' if i % 4 else 'oral only'}. "
            f"Typical Sites: {CITIES[i % len(CITIES)]} and {CITIES[(i + 3) % len(CITIES)]}."
        )
    return "\n".join(rows)


def _forms() -> str:
    return "\n".join([
        "SCHEDULE 13 - STANDARD FORMS",
        "",
        "Form 1 - Leave application. Worker number: ____. Trade: ____. Site: ____. Type of leave (annual / sick / emergency): ____. From: ____ To: ____. "
        "Reason: ____. Contact address during leave: ____. Supervisor's recommendation: ____. Approved by the site manager: ____. Date: ____.",
        "",
        "Form 2 - Grievance. Worker number: ____. Site: ____. Describe the problem (pay, hours, accommodation, treatment, safety, other): ____. "
        "When did it start? ____. Who have you told already? ____. What would you like the Company to do? ____. Received by: ____. Date received: ____. "
        "The Company will answer in writing within ten (10) Business Days.",
        "",
        "Form 3 - Accident and incident report. Date and time: ____. Site and exact place: ____. Persons involved (worker numbers only): ____. "
        "What happened: ____. Injuries and first aid given: ____. Taken to clinic or hospital (yes / no, where): ____. Witnesses (worker numbers): ____. "
        "Immediate action taken: ____. Root cause found by investigation: ____. Corrective action and person responsible: ____. Closed by HSE officer: ____.",
        "",
        "Form 4 - Overtime approval. Site: ____. Date: ____. Workers and hours (worker numbers only): ____. Reason for overtime: ____. "
        "Approved in advance by the Supervisor: ____. Confirmed after completion: ____. Sent to payroll on: ____.",
        "",
        "Form 5 - PPE issue record. Worker number: ____. Items issued (from Schedule 3): ____. Size: ____. Date issued: ____. "
        "Signature or thumbprint of the Worker: ____. Issued by: ____. Next replacement due: ____.",
        "",
        "Form 6 - Exit clearance. Worker number: ____. Last day worked: ____. Tools and PPE returned: ____. Camp room cleared: ____. "
        "Final pay computed and checked by: ____. Ticket booked: ____. Documents handed over: ____. Exit visa issued: ____.",
        "",
        "Form 7 - Training attendance. Course (from Schedule 7): ____. Date: ____. Trainer: ____. Workers attending (worker numbers): ____. "
        "Assessment result: ____. Certificate numbers issued: ____.",
        "",
        "Form 8 - Site transfer notice. Worker number: ____. From Site: ____. To Site: ____. Date of transfer: ____. "
        "Transport arranged: ____. Camp changed (yes / no): ____. Notified by: ____.",
    ])


def _definitions() -> str:
    lines = ["PART 1 - DEFINITIONS AND INTERPRETATION", ""]
    for i, (term, meaning) in enumerate(DEFINITIONS, 1):
        lines.append(f'1.{i} "{term}" means {meaning}.')
    lines.append(f"1.{len(DEFINITIONS) + 1} Headings are for convenience only. Words in the singular include the plural, and a reference to a clause or Schedule is to a clause of or Schedule to this Agreement.")
    return "\n".join(lines)


def _rate_card() -> str:
    rows = ["SCHEDULE 1 - TRADES, GRADES AND MONTHLY RATES", "",
            "Grade | Trade | Basic Salary (SAR) | Food Allowance (SAR) | Overtime rate (SAR/hour) | Trade test required"]
    rows[-1] = "Grade | Trade | Region | Basic Salary (SAR) | Food Allowance (SAR) | Overtime rate (SAR/hour) | Trade test required"
    for i, trade in enumerate(TRADES):
        grade = f"G-{i // 5 + 1:02d}"
        basic = 1000 if i < 20 else 1000 + 50 * (i % 6)
        for j, region in enumerate(REGIONS):
            pay = basic + 50 * j if basic > 1000 else basic
            rows.append(f"{grade} | {trade} | {region} | {pay:,} | {200 + 25 * ((i + j) % 3)} | {round(pay / 240 * 1.5, 2)} | {'yes' if i % 4 else 'no'}")
    rows.append("")
    rows.append("Notes: the Basic Salary is payable monthly in arrears. Allowances are paid only for days actually worked. Overtime is paid only when approved in writing by the Supervisor before it is worked.")
    return "\n".join(rows)


def _sites() -> str:
    rows = ["SCHEDULE 2 - SITES", "", "Site code | City | Type of work | Approximate headcount | Shift pattern"]
    kinds = ["residential tower", "hospital facilities management", "school maintenance", "warehouse fit-out", "road works camp", "mall cleaning", "district cooling plant", "villa compound"]
    for i in range(84):
        rows.append(f"S-{i + 1:03d} | {CITIES[i % len(CITIES)]} | {kinds[i % len(kinds)]} | {20 + (i * 7) % 90} | {'day' if i % 3 else 'day and night'}")
    rows.append("")
    rows.append("The Company may add, close or change Sites by written notice. A Worker may be moved between Sites within the Kingdom without his consent.")
    return "\n".join(rows)


def _ppe() -> str:
    rows = ["SCHEDULE 3 - PERSONAL PROTECTIVE EQUIPMENT", "", "Item | Issued to | Replacement interval"]
    for i, item in enumerate(PPE):
        rows.append(f"{item} | {'all Workers' if i % 3 == 0 else 'Workers in trades that need it'} | {['3 months', '6 months', '12 months', 'when worn'][i % 4]}")
    rows.append("")
    rows.append("PPE remains the property of the Company and shall be returned at the end of the Contract Term. No charge shall be made for PPE lost through fair wear and tear.")
    return "\n".join(rows)


def _discipline() -> str:
    items = [
        "Late arrival at the Site without a reasonable excuse: written warning; on the third occasion, deduction of one hour's pay.",
        "Absence without notice for one day: deduction of the day's pay and a written warning.",
        "Sleeping on duty: written warning; on repetition, deduction of one day's pay.",
        "Smoking outside marked areas: written warning.",
        "Failure to wear required PPE: written warning; on repetition, suspension for one day without pay.",
        "Fighting or threatening behaviour at a Site or in the Camp: final written warning or dismissal after investigation.",
        "Absconding. A Worker who leaves the worksite or the Camp without the Company's written permission for more than three (3) days shall be deemed to have absconded. The absconding Worker shall pay the Company liquidated damages of SAR 10,000 together with all outstanding Recruitment Costs, and the Company may report him to the authorities as absconded and withhold any wages due to him until the full sum is paid.",
        "Damage to Company property through negligence: the Worker pays the cost of repair, recovered from his salary.",
        "Theft or fraud: dismissal without notice or end-of-service benefits, and a report to the police.",
        "Possession or use of alcohol or drugs: dismissal without notice and a report to the authorities.",
        "Disclosure of Confidential Information: final written warning or dismissal.",
        "Every penalty shall be recorded in writing, and the Worker shall be given an opportunity to explain before it is imposed.",
    ]
    rows = ["SCHEDULE 4 - DISCIPLINARY CODE", ""]
    rows += [f"4.{i} {t}" for i, t in enumerate(items, 1)]
    return "\n".join(rows)


def _accommodation() -> str:
    items = [
        "Not more than eight (8) Workers per room, with at least four (4) square metres of floor space per Worker.",
        "A separate bed and a lockable cupboard for each Worker.",
        "Air conditioning in every room, maintained in working order.",
        "One toilet and one shower for every eight (8) Workers, cleaned daily.",
        "A kitchen with gas or electric cookers, sinks and refrigerators, or a canteen.",
        "Drinking water tested every three (3) months.",
        "Fire extinguishers, smoke detectors and marked emergency exits on every floor.",
        "A first-aid kit and a trained first-aider on each shift.",
        "Laundry facilities or a laundry service.",
        "A prayer area and a recreation room with television.",
        "Pest control at least monthly.",
        "Wi-Fi in common areas so that Workers can contact their families.",
        "A notice board in English, Bangla and Arabic showing the Company's grievance contacts and the labour office hotline.",
        "Separate accommodation for female workers, where any are employed.",
        "Transport between the Camp and the Site in vehicles meeting clause 7.14.",
    ]
    rows = ["SCHEDULE 5 - ACCOMMODATION STANDARDS", ""]
    rows += [f"5.{i} {t}" for i, t in enumerate(items, 1)]
    return "\n".join(rows)


def _mobilisation() -> str:
    rows = ["SCHEDULE 6 - MOBILISATION TIMELINE", "", "Step | Responsible | Target (days after demand letter)"]
    steps = [
        ("Demand letter and power of attorney issued", "Company"), ("Demand letter attested by the Bangladesh mission", "Agency"),
        ("Recruitment permission from the Bureau", "Agency"), ("Advertisement and shortlisting", "Agency"), ("Trade test", "Agency and Company"),
        ("Interview by Company representative", "Company"), ("Medical examination (GAMCA)", "Agency"), ("Visa application", "Agency"),
        ("Visa stamping", "Agency"), ("Pre-departure orientation", "Agency"), ("Emigration clearance and smart card", "Agency"),
        ("Insurance enrolment", "Agency"), ("Air ticket to the Kingdom", "Company"), ("Arrival and airport pick-up", "Company"),
        ("Medical test in the Kingdom", "Company"), ("Iqama issue", "Company"), ("Bank account opening (payroll card)", "Company"),
        ("Site induction", "Company"), ("Trade confirmation after probation", "Company"),
    ]
    for i, (step, who) in enumerate(steps, 1):
        rows.append(f"{step} | {who} | {7 * i}")
    return "\n".join(rows)


def _training() -> str:
    rows = ["SCHEDULE 7 - TRAINING PLAN", "", "Course | Duration (hours) | When | Delivered by"]
    for i, c in enumerate(COURSES):
        rows.append(f"{c} | {2 + i % 4} | {'first week' if i < 8 else 'first three months'} | {'Company HSE officer' if i % 2 else 'external trainer'}")
    rows.append("")
    rows.append("Training is given during working hours and paid as normal working time. Certificates are issued to each Worker and kept in the Worker's file.")
    return "\n".join(rows)


def build() -> str:
    parts = [
        "MANPOWER SUPPLY AND EMPLOYMENT AGREEMENT",
        "",
        "This Agreement is made between Meghna Bridge Overseas Ltd. (fictional), RL No. 0000 (fictional), Purana Paltan, Dhaka, Bangladesh (the \"Agency\"), "
        "and Najd Crest Facilities Services Co. (fictional), Riyadh, Kingdom of Saudi Arabia (the \"Company\"). It sets the terms on which the Agency recruits "
        "Bangladeshi workers for the Company and the terms of each Worker's employment with the Company in the Kingdom of Saudi Arabia.",
        "",
        _definitions(),
        "",
        "PART 2 - SUPPLY OF WORKERS",
        "",
        "2.1 The Company appoints the Agency to recruit Workers in Bangladesh for employment at the Sites, and the Agency accepts the appointment.",
        "2.2 The Company shall issue a demand letter stating the number of Workers, their trades, the Basic Salary for each trade and the Contract Term.",
        "2.3 The Agency shall obtain every permission required by the law of Bangladesh before advertising or selecting any Worker.",
        "2.4 The Agency shall select Workers through trade tests and interviews, and the Company may send a representative to attend them.",
        "2.5 The Agency shall issue a Mobilisation Schedule for each batch of Workers following the timeline in Schedule 6.",
        "2.6 The Agency shall ensure that each Worker has a valid passport, a medical fitness certificate and emigration clearance before departure.",
        "2.7 The Agency shall give each Worker a pre-departure orientation on the Kingdom, the Site rules and this Agreement.",
        "2.8 If a Worker leaves during the Probation Period, the Agency shall supply a Replacement Worker within sixty (60) days.",
        "2.9 The Company shall pay the Agency a Service Fee of SAR 1,500 per Worker within thirty (30) days of the Worker's arrival.",
        "2.10 The Agency shall not take any money from a Worker except as allowed by the law of Bangladesh.",
        "2.11 The Agency shall keep a copy of each Worker's employment terms and send a copy to the authorities as the law requires.",
        "2.12 Each Party shall comply with the laws of Bangladesh and of the Kingdom applicable to its obligations under this Agreement.",
        "",
        "PART 3 - THE WORKER'S DOCUMENTS AND OBLIGATIONS",
        "",
        "3.1 The Worker shall work diligently in his trade at any Site to which he is assigned and follow the reasonable instructions of his Supervisor.",
        "3.2 The Worker shall respect the laws, customs and religion of the Kingdom.",
        "3.3 The Worker shall keep his identity card and Site pass with him while at a Site.",
        "3.4 Passport. On arrival in the Kingdom the Worker shall deposit his passport with the Company, which shall keep it in safe custody for the whole Contract Term and release it only on final exit.",
        "3.5 The Worker shall not work for any other person during the Contract Term.",
        "3.6 The Worker shall attend the medical examinations the Company requires.",
        "3.7 The Worker shall take care of Company property, tools and vehicles entrusted to him.",
        "3.8 The Worker shall inform the Company within seven (7) days of any change in his family contact details.",
        "",
        "PART 4 - REMUNERATION AND DEDUCTIONS",
        "",
        "4.1 The Company shall pay the Worker the Basic Salary for his trade stated in Schedule 1. For a General Labourer the Basic Salary is SAR 1,000 (Saudi Riyals One Thousand) per month.",
        "4.2 Salary is paid monthly in arrears by bank transfer or payroll card not later than the seventh (7th) day of the following month.",
        "4.3 The Company shall give each Worker a monthly pay slip showing the Basic Salary, Allowances, Overtime and every deduction.",
        "4.4 Deductions. The Worker agrees that the following amounts shall be deducted from his monthly salary:",
        "(a) recovery of recruitment, visa and agency costs of SAR 4,800, at SAR 400 per month for 12 months;",
        "(b) accommodation charge of SAR 150 per month;",
        "(c) food charge of SAR 100 per month.",
        "4.5 Overtime approved in writing is paid at the rate in Schedule 1.",
        "4.6 The Company may change the date of payment by giving one month's written notice.",
        "4.7 Any amount the Worker owes the Company may be set off against his salary.",
        "4.8 Residence Permit. The Worker shall pay the cost of renewing his iqama (residence permit) and work permit every year.",
        "",
        "PART 5 - WORKING TIME AND LEAVE",
        "",
        "5.1 Normal working hours are eight (8) hours per day and forty-eight (48) hours per week, reduced to six (6) hours per day during Ramadan for Muslim Workers.",
        "5.2 Friday is the weekly rest day unless the Supervisor assigns another day.",
        "5.3 The Worker is entitled to twenty-one (21) days of paid annual leave after one year of service.",
        "5.4 The Worker is entitled to paid sick leave on a medical certificate in accordance with the law of the Kingdom.",
        "5.5 The Worker may take leave only on dates approved by the Company.",
        "",
        "PART 6 - ACCOMMODATION, TRANSPORT AND MEDICAL CARE",
        "",
        "6.1 The Company shall provide accommodation meeting the Accommodation Standards in Schedule 5.",
        "6.2 The Company shall provide daily transport between the Camp and the Site.",
        "6.3 The Company shall provide medical insurance for each Worker as required by the law of the Kingdom.",
        "6.4 The Company shall provide the air ticket from Dhaka to Riyadh.",
        "",
        "PART 7 - HEALTH AND SAFETY",
        "",
        *[f"7.{i} {t}" for i, t in enumerate(HSE, 1)],
        "",
        "PART 8 - CONDUCT AND DISCIPLINE",
        "",
        "8.1 The Disciplinary Code in Schedule 4 forms part of this Agreement and binds every Worker.",
        "8.2 The Supervisor may issue verbal and written warnings. Deductions and dismissals are decided by the Company's site manager.",
        "8.3 A Worker may appeal a penalty in writing to the Company's human resources manager within seven (7) days.",
        "",
        "PART 9 - TERMINATION",
        "",
        "9.1 Either Party may end a Worker's employment during the Probation Period without notice.",
        "9.2 The Company may terminate a Worker's employment at any time without notice if the Worker is found unsuitable.",
        "9.3 The Worker may resign by giving the Company two (2) months' written notice.",
        "9.4 The employment ends automatically on the expiry of the Contract Term unless renewed in writing.",
        "9.5 On termination the Company shall pay all wages due up to the last day worked, less any amounts owed by the Worker.",
        "9.6 Travel. The Worker shall bear the cost of his own return ticket to Bangladesh at the end of this Contract.",
        "",
        "PART 10 - END OF SERVICE",
        "",
        "10.1 The Worker shall not be entitled to any end-of-service award or gratuity on the completion or termination of this Contract.",
        "10.2 The Company shall issue a service certificate on request.",
        "",
        "PART 11 - COMPLAINTS, DISPUTES AND GOVERNING LAW",
        "",
        "11.1 Complaints and Disputes. The Worker waives all claims against the Company and the Agency that are not raised in writing within seven (7) days, and shall not file any complaint or case with BMET, the Bangladesh Embassy or any court in Bangladesh in respect of this Contract.",
        "11.2 Disputes between the Agency and the Company shall be settled amicably, failing which by the competent courts of Riyadh.",
        "11.3 This Agreement is governed by the laws of the Kingdom of Saudi Arabia.",
        "11.4 The Parties shall cooperate with any inquiry by the authorities of Bangladesh or the Kingdom about the Workers.",
        "",
        "PART 12 - GENERAL",
        "",
        *[f"12.{i} {name}. {text}" for i, (name, text) in enumerate(GENERAL, 1)],
        "",
        _rate_card(),
        "",
        _sites(),
        "",
        _ppe(),
        "",
        _discipline(),
        "",
        _accommodation(),
        "",
        _mobilisation(),
        "",
        _training(),
        "",
        _site_rules(),
        "",
        _kpis(),
        "",
        _pay_examples(),
        "",
        _camp_rules(),
        "",
        _job_descriptions(),
        "",
        _forms(),
        "",
        _annex_terms(),
        "",
        "Signed for the Agency ____________   Signed for the Company ____________",
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    text = build()
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(text):,} chars, about {len(text) // 2500} pages)")


if __name__ == "__main__":
    main()
