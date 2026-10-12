# -*- coding: utf-8 -*-
"""Idioma de cada ejemplar, de tres fuentes, por este orden:

  1. El catálogo MARC (008/35-37), si se ha extraído (ver marc.py) y el
     código es válido: describe el ejemplar concreto y cubre casi todo el
     fondo, también lo antiguo.
  2. La ficha de DILVE del libro (por ISBN, de lo ya descargado: aquí no se
     llama a DILVE): cubre las novedades aún sin catalogar y corrige los
     errores de catalogación («esp» en vez de «spa»).
  3. La signatura, cuando lo dice sin duda: su primera palabra es una marca
     de lengua («EUS N ATX», «ENG I1 ALO»).

Si ninguna lo dice, queda como «Sin determinar»: nunca se inventa.

DILVE (ONIX) y MARC usan los mismos códigos ISO 639-2/B: el euskera es "baq"
(o "eus"), el francés "fre" (o "fra"), el alemán "ger" (o "deu").
"""

IDIOMAS_MARC = {
    "aar": "Afar", "abk": "Abjasio", "ace": "Achenés", "ach": "Acoli", "ada": "Adangme", "ady": "Adigué",
    "afa": "Lenguas afroasiáticas", "afh": "Afrihili", "afr": "Afrikáans", "ain": "Ainu", "aka": "Akan",
    "akk": "Acadio", "alb": "Albanés", "ale": "Aleutiano", "alg": "Lenguas algonquinas", "alt": "Altái meridional",
    "amh": "Amárico", "ang": "Inglés antiguo", "anp": "Angika", "apa": "Lenguas apache", "ara": "Árabe",
    "arc": "Arameo", "arg": "Aragonés", "arm": "Armenio", "arn": "Mapuche", "arp": "Arapaho",
    "art": "Lenguas artificiales", "arw": "Arahuaco", "asm": "Asamés", "ast": "Asturiano",
    "ath": "Lenguas atapascanas", "aus": "Lenguas australianas", "ava": "Avar", "ave": "Avéstico", "awa": "Avadhi",
    "aym": "Aimara", "aze": "Azerbaiyano", "bad": "Lenguas banda", "bai": "Lenguas bamileke", "bak": "Baskir",
    "bal": "Baluchi", "bam": "Bambara", "ban": "Balinés", "baq": "Euskera", "bas": "Basaa",
    "bat": "Lenguas bálticas", "bej": "Beja", "bel": "Bielorruso", "bem": "Bemba", "ben": "Bengalí",
    "ber": "Lenguas beréberes", "bho": "Bhoyapurí", "bih": "Lenguas bihari", "bik": "Bicol", "bin": "Bini",
    "bis": "Bislama", "bla": "Siksika", "bnt": "Lenguas bantúes", "bod": "Tibetano", "bos": "Bosnio",
    "bra": "Braj", "bre": "Bretón", "btk": "Lenguas batak", "bua": "Buriato", "bug": "Buginés", "bul": "Búlgaro",
    "bur": "Birmano", "byn": "Blin", "cad": "Caddo", "cai": "Lenguas indígenas de América Central",
    "car": "Caribe", "cat": "Catalán", "cau": "Lenguas caucásicas", "ceb": "Cebuano", "cel": "Lenguas célticas",
    "ces": "Checo", "cha": "Chamorro", "chb": "Chibcha", "che": "Checheno", "chg": "Chagatái", "chi": "Chino",
    "chk": "Trukés", "chm": "Marí", "chn": "Jerga chinuk", "cho": "Choctaw", "chp": "Chipewyan", "chr": "Cheroqui",
    "chu": "Eslavo eclesiástico", "chv": "Chuvasio", "chy": "Cheyene", "cmc": "Lenguas chamicas", "cop": "Copto",
    "cor": "Córnico", "cos": "Corso", "cpe": "Criollos y pidgins de base inglesa",
    "cpf": "Criollos y pidgins de base francesa", "cpp": "Criollos y pidgins de base portuguesa", "cre": "Cree",
    "crh": "Tártaro de Crimea", "crp": "Criollos y pidgins", "csb": "Casubio", "cus": "Lenguas cusitas",
    "cym": "Galés", "cze": "Checo", "dak": "Dakota", "dan": "Danés", "dar": "Dargva",
    "day": "Lenguas dayak terrestres", "del": "Delaware", "den": "Slave", "deu": "Alemán", "dgr": "Dogrib",
    "din": "Dinka", "div": "Divehi", "doi": "Dogri", "dra": "Lenguas dravídicas", "dsb": "Bajo sorbio",
    "dua": "Duala", "dum": "Neerlandés medio", "dut": "Neerlandés", "dyu": "Diula", "dzo": "Dzongkha",
    "efi": "Efik", "egy": "Egipcio antiguo", "eka": "Ekajuk", "ell": "Griego", "elx": "Elamita", "eng": "Inglés",
    "enm": "Inglés medio", "epo": "Esperanto", "est": "Estonio", "eus": "Euskera", "ewe": "Ewé", "ewo": "Ewondo",
    "fan": "Fang", "fao": "Feroés", "fas": "Persa", "fat": "Fanti", "fij": "Fiyiano", "fil": "Filipino",
    "fin": "Finés", "fiu": "Lenguas fino-úgrias", "fon": "Fon", "fra": "Francés", "fre": "Francés",
    "frm": "Francés medio", "fro": "Francés antiguo", "frr": "Frisón septentrional", "frs": "Frisón oriental",
    "fry": "Frisón occidental", "ful": "Fula", "fur": "Friulano", "gaa": "Ga", "gay": "Gayo", "gba": "Gbaya",
    "gem": "Lenguas germánicas", "geo": "Georgiano", "ger": "Alemán", "gez": "Geez", "gil": "Gilbertés",
    "gla": "Gaélico escocés", "gle": "Irlandés", "glg": "Gallego", "glv": "Manés", "gmh": "Alto alemán medio",
    "goh": "Alto alemán antiguo", "gon": "Gondi", "gor": "Gorontalo", "got": "Gótico", "grb": "Grebo",
    "grc": "Griego clásico", "gre": "Griego", "grn": "Guaraní", "gsw": "Alemán suizo", "guj": "Guyaratí",
    "gwi": "Kutchin", "hai": "Haida", "hat": "Criollo haitiano", "hau": "Hausa", "haw": "Hawaiano",
    "heb": "Hebreo", "her": "Herero", "hil": "Hiligaynon", "him": "Lenguas himachalíes", "hin": "Hindi",
    "hit": "Hitita", "hmn": "Hmong", "hmo": "Hiri motu", "hrv": "Croata", "hsb": "Alto sorbio", "hun": "Húngaro",
    "hup": "Hupa", "hye": "Armenio", "iba": "Iban", "ibo": "Igbo", "ice": "Islandés", "ido": "Ido",
    "iii": "Yi de Sichuán", "ijo": "Lenguas ijo", "iku": "Inuktitut", "ile": "Interlingue", "ilo": "Ilocano",
    "ina": "Interlingua", "inc": "Lenguas índicas", "ind": "Indonesio", "ine": "Lenguas indoeuropeas",
    "inh": "Ingush", "ipk": "Inupiaq", "ira": "Lenguas iranias", "iro": "Lenguas iroquesas", "isl": "Islandés",
    "ita": "Italiano", "jav": "Javanés", "jbo": "Lojban", "jpn": "Japonés", "jpr": "Judeo-persa",
    "jrb": "Judeo-árabe", "kaa": "Karakalpako", "kab": "Cabileño", "kac": "Kachin", "kal": "Groenlandés",
    "kam": "Kamba", "kan": "Canarés", "kar": "Lenguas karen", "kas": "Cachemir", "kat": "Georgiano",
    "kau": "Kanuri", "kaw": "Kawi", "kaz": "Kazajo", "kbd": "Kabardiano", "kha": "Khasi",
    "khi": "Lenguas joisanas", "khm": "Jemer", "kho": "Kotanés", "kik": "Kikuyu", "kin": "Kinyarwanda",
    "kir": "Kirguís", "kmb": "Kimbundu", "kok": "Konkaní", "kom": "Komi", "kon": "Kongo", "kor": "Coreano",
    "kos": "Kosraeano", "kpe": "Kpelle", "krc": "Karachay-balkar", "krl": "Carelio", "kro": "Lenguas kru",
    "kru": "Kurukh", "kua": "Kuanyama", "kum": "Kumyk", "kur": "Kurdo", "kut": "Kutenai", "lad": "Ladino",
    "lah": "Lahnda", "lam": "Lamba", "lao": "Lao", "lat": "Latín", "lav": "Letón", "lez": "Lezgiano",
    "lim": "Limburgués", "lin": "Lingala", "lit": "Lituano", "lol": "Mongo", "loz": "Lozi", "ltz": "Luxemburgués",
    "lua": "Luba-lulua", "lub": "Luba-katanga", "lug": "Ganda", "lui": "Luiseño", "lun": "Lunda",
    "luo": "Luo (Kenia y Tanzania)", "lus": "Mizo", "mac": "Macedonio", "mad": "Madurés", "mag": "Magahi",
    "mah": "Marshalés", "mai": "Maithili", "mak": "Macasar", "mal": "Malayálam", "man": "Mandingo", "mao": "Maorí",
    "map": "Lenguas austronésicas", "mar": "Maratí", "mas": "Masái", "may": "Malayo", "mdf": "Moksha",
    "mdr": "Mandar", "men": "Mende", "mga": "Irlandés medio", "mic": "Micmac", "min": "Minangkabau",
    "mis": "Lenguas sin codificar", "mkd": "Macedonio", "mkh": "Lenguas mon-jemer", "mlg": "Malgache",
    "mlt": "Maltés", "mnc": "Manchú", "mni": "Manipurí", "mno": "Lenguas manobo", "moh": "Mohawk", "mon": "Mongol",
    "mos": "Mossi", "mri": "Maorí", "msa": "Malayo", "mul": "Multilingüe", "mun": "Lenguas munda", "mus": "Creek",
    "mwl": "Mirandés", "mwr": "Marwari", "mya": "Birmano", "myn": "Lenguas mayas", "myv": "Erzya",
    "nah": "Lenguas náhuatl", "nai": "Lenguas indígenas de América del Norte", "nap": "Napolitano",
    "nau": "Nauruano", "nav": "Navajo", "nbl": "Ndebele meridional", "nde": "Ndebele septentrional",
    "ndo": "Ndonga", "nds": "Bajo alemán", "nep": "Nepalí", "new": "Nevarí", "nia": "Nias",
    "nic": "Lenguas nígero-kordofanesas", "niu": "Niueano", "nld": "Neerlandés", "nno": "Noruego nynorsk",
    "nob": "Noruego bokmal", "nog": "Nogai", "non": "Nórdico antiguo", "nor": "Noruego", "nqo": "N'ko",
    "nso": "Sotho septentrional", "nub": "Lenguas nubias", "nwc": "Newari clásico", "nya": "Nyanja",
    "nym": "Nyamwezi", "nyn": "Nyankole", "nyo": "Nyoro", "nzi": "Nzima", "oci": "Occitano", "oji": "Ojibwa",
    "ori": "Oriya", "orm": "Oromo", "osa": "Osage", "oss": "Osético", "ota": "Turco otomano",
    "oto": "Lenguas otomíes", "paa": "Lenguas papúes", "pag": "Pangasinán", "pal": "Pahlavi", "pam": "Pampanga",
    "pan": "Punyabí", "pap": "Papiamento", "pau": "Palauano", "peo": "Persa antiguo", "per": "Persa",
    "phi": "Lenguas filipinas", "phn": "Fenicio", "pli": "Pali", "pol": "Polaco", "pon": "Pohnpeiano",
    "por": "Portugués", "pra": "Lenguas prácritas", "pro": "Provenzal antiguo", "pus": "Pastún", "que": "Quechua",
    "raj": "Rajasthani", "rap": "Rapanui", "rar": "Rarotongano", "roa": "Lenguas romances", "roh": "Romanche",
    "rom": "Romaní", "ron": "Rumano", "rum": "Rumano", "run": "Kirundi", "rup": "Arrumano", "rus": "Ruso",
    "sad": "Sandawe", "sag": "Sango", "sah": "Sakha", "sai": "Lenguas indígenas de América del Sur",
    "sal": "Lenguas salish", "sam": "Arameo samaritano", "san": "Sánscrito", "sas": "Sasak", "sat": "Santali",
    "scn": "Siciliano", "sco": "Escocés", "sel": "Selkup", "sem": "Lenguas semíticas", "sga": "Irlandés antiguo",
    "sgn": "Lenguas de signos", "shn": "Shan", "sid": "Sidamo", "sin": "Cingalés", "sio": "Lenguas siux",
    "sit": "Lenguas sinotibetanas", "sla": "Lenguas eslavas", "slk": "Eslovaco", "slo": "Eslovaco",
    "slv": "Esloveno", "sma": "Sami meridional", "sme": "Sami septentrional", "smi": "Lenguas sami",
    "smj": "Sami lule", "smn": "Sami inari", "smo": "Samoano", "sms": "Sami skolt", "sna": "Shona", "snd": "Sindi",
    "snk": "Soninké", "sog": "Sogdiano", "som": "Somalí", "son": "Lenguas songhai", "sot": "Sotho meridional",
    "spa": "Castellano", "sqi": "Albanés", "srd": "Sardo", "srn": "Sranan tongo", "srp": "Serbio", "srr": "Serer",
    "ssa": "Lenguas nilo-saharianas", "ssw": "Suazi", "suk": "Sukuma", "sun": "Sundanés", "sus": "Susu",
    "sux": "Sumerio", "swa": "Suajili", "swe": "Sueco", "syc": "Siríaco clásico", "syr": "Siriaco",
    "tah": "Tahitiano", "tai": "Lenguas tai", "tam": "Tamil", "tat": "Tártaro", "tel": "Telugu", "tem": "Temne",
    "ter": "Tereno", "tet": "Tetún", "tgk": "Tayiko", "tgl": "Tagalo", "tha": "Tailandés", "tib": "Tibetano",
    "tig": "Tigré", "tir": "Tigriña", "tiv": "Tiv", "tkl": "Tokelauano", "tlh": "Klingon", "tli": "Tlingit",
    "tmh": "Tamashek", "tog": "Tonga del Nyasa", "ton": "Tongano", "tpi": "Tok pisin", "tsi": "Tsimshiano",
    "tsn": "Setsuana", "tso": "Tsonga", "tuk": "Turcomano", "tum": "Tumbuka", "tup": "Lenguas tupí",
    "tur": "Turco", "tut": "Lenguas altaicas", "tvl": "Tuvaluano", "twi": "Twi", "tyv": "Tuviniano",
    "udm": "Udmurt", "uga": "Ugarítico", "uig": "Uigur", "ukr": "Ucraniano", "umb": "Umbundu",
    "und": "Indeterminado", "urd": "Urdu", "uzb": "Uzbeko", "vai": "Vai", "ven": "Venda", "vie": "Vietnamita",
    "vol": "Volapük", "vot": "Vótico", "wak": "Lenguas wakash", "wal": "Wolayta", "war": "Waray", "was": "Washo",
    "wel": "Galés", "wen": "Lenguas sorabas", "wln": "Valón", "wol": "Wólof", "xal": "Kalmyk", "xho": "Xhosa",
    "yao": "Yao", "yap": "Yapés", "yid": "Yidis", "yor": "Yoruba", "ypk": "Lenguas yupik", "zap": "Zapoteco",
    "zbl": "Símbolos Bliss", "zen": "Zenaga", "zgh": "Tamazight estándar marroquí", "zha": "Zhuang",
    "zho": "Chino", "znd": "Lenguas zande", "zul": "Zulú", "zun": "Zuñi", "zxx": "Sin contenido textual",
    "zza": "Zazaki",
}
IDIOMA_SIN_DATO = "Sin determinar"

IDIOMAS_LABELS_EU = {
    "Abjasio": "Abkhaziera", "Achenés": "Acehnera", "Acoli": "Acholiera", "Adangme": "Adangmera",
    "Adigué": "Adigera", "Afar": "Afarera", "Afrikáans": "Afrikaansa", "Aimara": "Aimara", "Ainu": "Ainuera",
    "Akan": "Akanera", "Albanés": "Albaniera", "Alemán": "Alemana", "Alemán suizo": "Suitzako alemana",
    "Aleutiano": "Aleutera", "Alto sorbio": "Goi-sorabiera", "Altái meridional": "Hegoaldeko altaiera",
    "Amárico": "Amharera", "Angika": "Angikera", "Aragonés": "Aragoiera", "Arapaho": "Arapahoera",
    "Armenio": "Armeniera", "Arrumano": "Aromaniera", "Asamés": "Assamera", "Asturiano": "Asturiera",
    "Avadhi": "Awadhiera", "Avar": "Avarera", "Azerbaiyano": "Azerbaijanera", "Bajo alemán": "Behe-alemana",
    "Bajo sorbio": "Behe-sorabiera", "Balinés": "Baliera", "Bambara": "Bambarera", "Basaa": "Basaa",
    "Baskir": "Baxkirera", "Bemba": "Bembera", "Bengalí": "Bengalera", "Bhoyapurí": "Bhojpurera",
    "Bielorruso": "Bielorrusiera", "Bini": "Edoera", "Birmano": "Birmaniera", "Bislama": "Bislama",
    "Blin": "Bilenera", "Bosnio": "Bosniera", "Bretón": "Bretoiera", "Buginés": "Buginera",
    "Búlgaro": "Bulgariera", "Cabileño": "Kabiliera", "Cachemir": "Kaxmirera", "Canarés": "Kannada",
    "Carelio": "Kareliera", "Castellano": "Gaztelania", "Catalán": "Katalana", "Cebuano": "Cebuanoera",
    "Chamorro": "Txamorroera", "Checheno": "Txetxenera", "Checo": "Txekiera", "Cheroqui": "Txerokiera",
    "Cheyene": "Txeieneera", "Chino": "Txinera", "Chipewyan": "Chipewyera", "Choctaw": "Txoktawera",
    "Chuvasio": "Txuvaxera", "Cingalés": "Sinhala", "Coreano": "Koreera", "Corso": "Korsikera",
    "Creek": "Muscogeera", "Criollo haitiano": "Haitiko kreolera", "Criollos y pidgins": "Kreolerak eta pidginak",
    "Criollos y pidgins de base francesa": "Frantsesean oinarritutako kreolerak",
    "Criollos y pidgins de base inglesa": "Ingelesean oinarritutako kreolerak",
    "Criollos y pidgins de base portuguesa": "Portugesean oinarritutako kreolerak", "Croata": "Kroaziera",
    "Córnico": "Kornubiera", "Dakota": "Dakotera", "Danés": "Daniera", "Dargva": "Darginera", "Divehi": "Dhivehia",
    "Dogri": "Dogria", "Dogrib": "Dogribera", "Duala": "Dualera", "Dzongkha": "Dzongkha", "Efik": "Efikera",
    "Ekajuk": "Ekajuka", "Erzya": "Erziera", "Escocés": "Eskoziera", "Eslavo eclesiástico": "Elizako eslaviera",
    "Eslovaco": "Eslovakiera", "Esloveno": "Esloveniera", "Esperanto": "Esperantoa", "Estonio": "Estoniera",
    "Euskera": "Euskara", "Ewondo": "Ewondoa", "Ewé": "Eweera", "Feroés": "Faroera", "Filipino": "Filipinera",
    "Finés": "Finlandiera", "Fiyiano": "Fijiera", "Fon": "Fonera", "Francés": "Frantsesa",
    "Frisón occidental": "Mendebaldeko frisiera", "Frisón septentrional": "Iparraldeko frisiera",
    "Friulano": "Friulera", "Fula": "Fula", "Ga": "Gaera", "Gallego": "Galiziera", "Galés": "Galesa",
    "Ganda": "Luganda", "Gaélico escocés": "Eskoziako gaelikoa", "Geez": "Ge'eza", "Georgiano": "Georgiera",
    "Gilbertés": "Kiribatiera", "Gorontalo": "Gorontaloera", "Griego": "Greziera",
    "Griego clásico": "Greziera klasikoa", "Groenlandés": "Groenlandiera", "Guaraní": "Guaraniera",
    "Guyaratí": "Gujaratera", "Haida": "Haidera", "Hausa": "Hausa", "Hawaiano": "Hawaiiera", "Hebreo": "Hebreera",
    "Herero": "Hereroera", "Hiligaynon": "Hiligaynonera", "Hindi": "Hindia", "Hmong": "Hmonga", "Hupa": "Hupera",
    "Húngaro": "Hungariera", "Iban": "Ibanera", "Ido": "Idoa", "Igbo": "Igboera", "Ilocano": "Ilocanoera",
    "Indeterminado": "Zehaztugabea", "Indonesio": "Indonesiera", "Inglés": "Ingelesa", "Ingush": "Ingushera",
    "Interlingua": "Interlingua", "Interlingue": "Interlinguea", "Inuktitut": "Inuitera", "Irlandés": "Irlandera",
    "Islandés": "Islandiera", "Italiano": "Italiera", "Japonés": "Japoniera", "Javanés": "Javera",
    "Jemer": "Khemerera", "Kabardiano": "Kabardiera", "Kachin": "Jingphoera", "Kalmyk": "Kalmykera",
    "Kamba": "Kambera", "Kanuri": "Kanuriera", "Karachay-balkar": "Karachayera-balkarera", "Kazajo": "Kazakhera",
    "Khasi": "Khasiera", "Kikuyu": "Kikuyuera", "Kimbundu": "Kimbundua", "Kinyarwanda": "Kinyaruanda",
    "Kirguís": "Kirgizera", "Kirundi": "Rundiera", "Klingon": "Klingonera", "Komi": "Komiera", "Kongo": "Kikongoa",
    "Konkaní": "Konkanera", "Kpelle": "Kpelleera", "Kuanyama": "Kuanyama", "Kumyk": "Kumykera",
    "Kurdo": "Kurduera", "Kurukh": "Kurukhera", "Kutchin": "Gwich'inera", "Ladino": "Ladinoa", "Lao": "Laosera",
    "Latín": "Latina", "Lenguas afroasiáticas": "Hizkuntza afroasiarrak",
    "Lenguas algonquinas": "Hizkuntza algonkinak", "Lenguas altaicas": "Hizkuntza altaikoak",
    "Lenguas apache": "Apatxe hizkuntzak", "Lenguas artificiales": "Hizkuntza artifizialak",
    "Lenguas atapascanas": "Hizkuntza atapaskarrak", "Lenguas australianas": "Australiako hizkuntzak",
    "Lenguas austronésicas": "Hizkuntza austronesiarrak", "Lenguas bamileke": "Bamileke hizkuntzak",
    "Lenguas banda": "Banda hizkuntzak", "Lenguas bantúes": "Bantu hizkuntzak",
    "Lenguas batak": "Batak hizkuntzak", "Lenguas beréberes": "Berbere hizkuntzak",
    "Lenguas bihari": "Bihar hizkuntzak", "Lenguas bálticas": "Hizkuntza baltikoak",
    "Lenguas caucásicas": "Kaukasoko hizkuntzak", "Lenguas chamicas": "Chamic hizkuntzak",
    "Lenguas cusitas": "Kuxita hizkuntzak", "Lenguas célticas": "Hizkuntza zeltak",
    "Lenguas dayak terrestres": "Lehorreko Dayak hizkuntzak", "Lenguas de signos": "Zeinu-hizkuntzak",
    "Lenguas dravídicas": "Hizkuntza dravidikoak", "Lenguas eslavas": "Hizkuntza eslaviarrak",
    "Lenguas filipinas": "Filipinetako hizkuntzak", "Lenguas fino-úgrias": "Fino-ugriar hizkuntzak",
    "Lenguas germánicas": "Hizkuntza germaniarrak", "Lenguas himachalíes": "Himachal hizkuntzak",
    "Lenguas ijo": "Ijo hizkuntzak", "Lenguas indoeuropeas": "Hizkuntza indoeuroparrak",
    "Lenguas indígenas de América Central": "Erdialdeko Amerikako hizkuntza indigenak",
    "Lenguas indígenas de América del Norte": "Ipar Amerikako hizkuntza indigenak",
    "Lenguas indígenas de América del Sur": "Hego Amerikako hizkuntza indigenak",
    "Lenguas iranias": "Hizkuntza iranikoak", "Lenguas iroquesas": "Irokes hizkuntzak",
    "Lenguas joisanas": "Khoisan hizkuntzak", "Lenguas karen": "Karen hizkuntzak", "Lenguas kru": "Kru hizkuntzak",
    "Lenguas manobo": "Manobo hizkuntzak", "Lenguas mayas": "Maia hizkuntzak",
    "Lenguas mon-jemer": "Mon-khmer hizkuntzak", "Lenguas munda": "Munda hizkuntzak",
    "Lenguas nilo-saharianas": "Nilo-saharar hizkuntzak", "Lenguas nubias": "Nubiar hizkuntzak",
    "Lenguas náhuatl": "Nahuatl hizkuntzak", "Lenguas nígero-kordofanesas": "Niger-Kordofan hizkuntzak",
    "Lenguas otomíes": "Otomi hizkuntzak", "Lenguas papúes": "Papuar hizkuntzak",
    "Lenguas prácritas": "Prakrito hizkuntzak", "Lenguas romances": "Hizkuntza erromantzeak",
    "Lenguas salish": "Salish hizkuntzak", "Lenguas sami": "Sami hizkuntzak",
    "Lenguas semíticas": "Hizkuntza semitikoak", "Lenguas sin codificar": "Kodifikatu gabeko hizkuntzak",
    "Lenguas sinotibetanas": "Sino-tibetar hizkuntzak", "Lenguas siux": "Sioux hizkuntzak",
    "Lenguas songhai": "Songhai hizkuntzak", "Lenguas sorabas": "Sorabiera hizkuntzak",
    "Lenguas tai": "Tai hizkuntzak", "Lenguas tupí": "Tupi hizkuntzak", "Lenguas wakash": "Wakash hizkuntzak",
    "Lenguas yupik": "Yupik hizkuntzak", "Lenguas zande": "Zande hizkuntzak",
    "Lenguas índicas": "Hizkuntza indikoak", "Letón": "Letoniera", "Lezgiano": "Lezginera",
    "Limburgués": "Limburgera", "Lingala": "Lingala", "Lituano": "Lituaniera", "Lojban": "Lojbana",
    "Lozi": "Loziera", "Luba-katanga": "Katangako lubera", "Luba-lulua": "Kasai mendebaldeko lubera",
    "Lunda": "Lundera", "Luo (Kenia y Tanzania)": "Luoera", "Luxemburgués": "Luxenburgera",
    "Macasar": "Makassarera", "Macedonio": "Mazedoniera", "Madurés": "Madurera", "Magahi": "Magadhera",
    "Maithili": "Maithilia", "Malayo": "Malaysiera", "Malayálam": "Malabarera", "Malgache": "Malgaxea",
    "Maltés": "Maltera", "Manipurí": "Manipurera", "Manés": "Manxera", "Maorí": "Maoriera",
    "Mapuche": "Mapudunguna", "Maratí": "Marathera", "Marshalés": "Marshallera", "Marí": "Mariera",
    "Masái": "Masaiera", "Mende": "Mendeera", "Micmac": "Mikmakera", "Minangkabau": "Minangkabauera",
    "Mirandés": "Mirandesa", "Mizo": "Mizoera", "Mohawk": "Mohawkera", "Moksha": "Mokxera", "Mongol": "Mongoliera",
    "Mossi": "Mossiera", "Multilingüe": "Eleaniztuna", "Napolitano": "Napoliera", "Nauruano": "Nauruera",
    "Navajo": "Navajoera", "Ndebele meridional": "Hegoaldeko ndebeleera",
    "Ndebele septentrional": "Iparraldeko ndebeleera", "Ndonga": "Ndonga", "Neerlandés": "Nederlandera",
    "Nepalí": "Nepalera", "Nevarí": "Newarera", "Nias": "Niasera", "Niueano": "Niueera", "Nogai": "Nogaiera",
    "Noruego": "Norvegiera", "Noruego bokmal": "Bokmål (norvegiera)", "Noruego nynorsk": "Nynorsk (norvegiera)",
    "Nyanja": "Chewera", "Nyankole": "Nkoreera", "N'ko": "N'koera", "Occitano": "Okzitaniera", "Oriya": "Oriya",
    "Oromo": "Oromoera", "Osético": "Osetiera", "Palauano": "Palauera", "Pampanga": "Pampangera",
    "Pangasinán": "Pangasinanera", "Papiamento": "Papiamentoa", "Pastún": "Paxtunera", "Persa": "Persiera",
    "Polaco": "Poloniera", "Portugués": "Portugesa", "Punyabí": "Punjabera", "Quechua": "Kitxua",
    "Rajasthani": "Rajastanera", "Rapanui": "Rapanuia", "Rarotongano": "Rarotongera",
    "Romanche": "Erretorromaniera", "Rumano": "Errumaniera", "Ruso": "Errusiera", "Sakha": "Sakhera",
    "Sami inari": "Inariko samiera", "Sami lule": "Luleko samiera", "Sami meridional": "Hegoaldeko samiera",
    "Sami septentrional": "Iparraldeko samiera", "Sami skolt": "Skolten samiera", "Samoano": "Samoera",
    "Sandawe": "Sandaweera", "Sango": "Sangoa", "Santali": "Santalera", "Sardo": "Sardiniera",
    "Serbio": "Serbiera", "Setsuana": "Tswanera", "Shan": "Shanera", "Shona": "Shonera", "Siciliano": "Siziliera",
    "Siksika": "Siksikera", "Sin contenido textual": "Testurik gabe", "Sin determinar": "Zehaztu gabe",
    "Sindi": "Sindhia", "Siriaco": "Asiriera", "Somalí": "Somaliera", "Soninké": "Soninkeera",
    "Sotho meridional": "Hegoaldeko sothoera", "Sotho septentrional": "Pediera", "Sranan tongo": "Sranan tongoa",
    "Suajili": "Swahilia", "Suazi": "Swatiera", "Sueco": "Suediera", "Sukuma": "Sukumera", "Sundanés": "Sundanera",
    "Sánscrito": "Sanskritoa", "Tagalo": "Tagaloa", "Tahitiano": "Tahitiera", "Tailandés": "Thailandiera",
    "Tamazight estándar marroquí": "Amazigera estandarra", "Tamil": "Tamilera", "Tayiko": "Tajikera",
    "Telugu": "Telugua", "Temne": "Temneera", "Tetún": "Tetuma", "Tibetano": "Tibetera", "Tigriña": "Tigrinyera",
    "Tigré": "Tigreera", "Tlingit": "Tlingitera", "Tok pisin": "Tok pisin", "Tongano": "Tongera",
    "Trukés": "Chuukera", "Tsonga": "Tsongera", "Tumbuka": "Tumbukera", "Turco": "Turkiera",
    "Turcomano": "Turkmenera", "Tuvaluano": "Tuvaluera", "Tuviniano": "Tuvera", "Twi": "Twia",
    "Tártaro": "Tatarera", "Ucraniano": "Ukrainera", "Udmurt": "Udmurtera", "Uigur": "Uigurrera",
    "Umbundu": "Umbundua", "Urdu": "Urdua", "Uzbeko": "Uzbekera", "Vai": "Vaiera", "Valón": "Valoniera",
    "Venda": "Vendera", "Vietnamita": "Vietnamera", "Volapük": "Volapük", "Waray": "Warayera",
    "Wolayta": "Wolayttera", "Wólof": "Wolofera", "Xhosa": "Xhosera", "Yi de Sichuán": "Sichuango yiera",
    "Yidis": "Yiddisha", "Yoruba": "Jorubera", "Zazaki": "Zazera", "Zhuang": "Zhuangera", "Zulú": "Zuluera",
    "Zuñi": "Zuñiera", "Árabe": "Arabiera",
}

_IDIOMAS_VALIDOS = set(IDIOMAS_MARC.values())


def nombre_idioma(cod):
    if not cod:
        return None
    cod = cod.lower().strip()
    return IDIOMAS_MARC.get(cod, f"Otro ({cod})")


def es_idioma_normalizado(idioma):
    """True si el idioma figura en la lista MARC de lenguas. Descarta «Sin
    determinar» y «Otro (xxx)», normalmente errores de catalogación."""
    return bool(idioma) and idioma in _IDIOMAS_VALIDOS


def traducir_idioma(nombre, idioma_ui="es"):
    """Etiqueta del idioma en la lengua de la interfaz. El valor interno se
    mantiene siempre en castellano, porque es la clave de agrupado."""
    if idioma_ui != "eu":
        return nombre
    return IDIOMAS_LABELS_EU.get(nombre, nombre)


# Primera palabra de la signatura que marca la lengua del documento. Solo la
# primera: en «342.7 EUS» o «025 FRA», EUS y FRA son el autor o el tema.
IDIOMA_POR_SIGNATURA = {
    "EUS": "baq", "EUSK": "baq", "ENG": "eng", "ING": "eng", "FRA": "fre", "FRE": "fre",
    "CAT": "cat", "GAL": "glg", "GLG": "glg", "ALE": "ger", "DEU": "ger", "GER": "ger",
    "ITA": "ita", "POR": "por",
}
# Códigos que no dicen el idioma: sin determinar, sin contenido lingüístico
_SIN_IDIOMA = {"und", "zxx", "mis"}


def idioma_de_signatura(signatura):
    """Código de la lengua si la primera palabra de la signatura la marca."""
    partes = str(signatura or "").split()
    return IDIOMA_POR_SIGNATURA.get(partes[0].upper()) if partes else None


def asignar_idiomas(registros, idiomas_dilve, idiomas_marc=None):
    """Pone a cada ejemplar su idioma y de dónde sale («marc», «dilve»,
    «signatura» o None).

    idiomas_dilve  {isbn: código} de las fichas de DILVE descargadas
    idiomas_marc   {código de barras: idioma} extraído del catálogo MARC

    Devuelve cuántos salen de cada sitio."""
    idiomas_marc = idiomas_marc or {}
    cuenta = {"total": len(registros), "marc": 0, "dilve": 0, "signatura": 0, "sin_dato": 0}
    for r in registros:
        nombre, origen = idiomas_marc.get(str(r.get("record_id"))), None
        if es_idioma_normalizado(nombre) and nombre != IDIOMAS_MARC.get("und"):
            origen = "marc"
        else:
            codigo = (idiomas_dilve.get(r.get("isbn")) or "").lower().strip() if r.get("isbn") else ""
            if codigo and codigo not in _SIN_IDIOMA:
                nombre, origen = nombre_idioma(codigo), "dilve"
            else:
                codigo = idioma_de_signatura(r.get("signatura_real"))
                if codigo:
                    nombre, origen = nombre_idioma(codigo), "signatura"
        r["idioma"] = nombre if origen else IDIOMA_SIN_DATO
        r["idioma_origen"] = origen
        cuenta[origen or "sin_dato"] += 1
    return cuenta
