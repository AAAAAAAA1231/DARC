from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_name(name: str) -> str:
    text = strip_accents(name or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # 去掉常见前缀/后缀噪音
    for token in (
        "cf", "fc", "cd", "ud", "rcd", "sd", "sc", "sv", "ss", "ac", "as", "us",
        "calcio", "club", "de", "the", "1", "04", "07", "05", "sport", "sports",
    ):
        text = re.sub(rf"\b{token}\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class TeamInfo:
    canonical: str
    name_cn: str
    aliases: tuple[str, ...]
    lat: float
    lon: float
    stadium: str


# 覆盖近几个赛季一二级别常见队名，保证升班马也能对齐。
TEAMS: tuple[TeamInfo, ...] = (
    # —— 西甲 / 西乙 ——
    TeamInfo("Alaves", "阿拉维斯", ("Alavés", "Deportivo Alaves", "ALA"), 42.867, -2.688, "Mendizorrotza"),
    TeamInfo("Athletic Club", "毕尔巴鄂竞技", ("Ath Bilbao", "Athletic Bilbao", "Bilbao", "ATH"), 43.264, -2.949, "San Mamés"),
    TeamInfo("Atletico Madrid", "马德里竞技", ("Ath Madrid", "Atlético Madrid", "Atletico", "ATM", "马竞"), 40.436, -3.599, "Civitas Metropolitano"),
    TeamInfo("Barcelona", "巴塞罗那", ("Barca", "FC Barcelona", "BAR", "巴萨"), 41.381, 2.123, "Spotify Camp Nou"),
    TeamInfo("Celta Vigo", "塞尔塔", ("Celta", "Celta de Vigo", "CEL"), 42.212, -8.740, "Abanca Balaídos"),
    TeamInfo("Deportivo", "拉科鲁尼亚", ("La Coruna", "Deportivo La Coruna", "Deportivo La Coruña", "DEP"), 43.369, -8.417, "Riazor"),
    TeamInfo("Elche", "埃尔切", ("Elche CF", "ELC"), 38.267, -0.663, "Martínez Valero"),
    TeamInfo("Espanyol", "西班牙人", ("Espanol", "RCD Espanyol", "ESP"), 41.348, 2.076, "RCDE Stadium"),
    TeamInfo("Getafe", "赫塔费", ("Getafe CF", "GET"), 40.326, -3.715, "Coliseum"),
    TeamInfo("Levante", "莱万特", ("Levante UD", "LEV"), 39.495, -0.359, "Ciutat de València"),
    TeamInfo("Malaga", "马拉加", ("Málaga", "Malaga CF", "MCF"), 36.734, -4.427, "La Rosaleda"),
    TeamInfo("Osasuna", "奥萨苏纳", ("CA Osasuna", "OSA"), 42.797, -1.637, "El Sadar"),
    TeamInfo("Racing Santander", "桑坦德竞技", ("Santander", "Racing", "RAC"), 43.438, -3.839, "El Sardinero"),
    TeamInfo("Rayo Vallecano", "巴列卡诺", ("Vallecano", "Rayo", "RAY"), 40.392, -3.659, "Vallecas"),
    TeamInfo("Real Betis", "皇家贝蒂斯", ("Betis", "BET", "贝蒂斯"), 37.356, -6.000, "Benito Villamarín"),
    TeamInfo("Real Madrid", "皇家马德里", ("Madrid", "RMA", "皇马"), 40.453, -3.688, "Santiago Bernabéu"),
    TeamInfo("Real Sociedad", "皇家社会", ("Sociedad", "RSO"), 43.301, -1.974, "Reale Arena"),
    TeamInfo("Sevilla", "塞维利亚", ("Sevilla FC", "SEV"), 37.384, -5.971, "Ramón Sánchez-Pizjuán"),
    TeamInfo("Valencia", "瓦伦西亚", ("Valencia CF", "VAL", "巴伦西亚"), 39.475, -0.358, "Mestalla"),
    TeamInfo("Villarreal", "比利亚雷亚尔", ("Villarreal CF", "VIL"), 39.944, -0.103, "Estadio de la Cerámica"),
    TeamInfo("Mallorca", "马略卡", ("RCD Mallorca",), 39.590, 2.630, "Son Moix"),
    TeamInfo("Girona", "赫罗纳", ("Girona FC",), 41.961, 2.828, "Montilivi"),
    TeamInfo("Las Palmas", "拉斯帕尔马斯", ("UD Las Palmas",), 28.100, -15.457, "Gran Canaria"),
    TeamInfo("Leganes", "莱加内斯", ("Leganés", "CD Leganes"), 40.328, -3.761, "Butarque"),
    TeamInfo("Valladolid", "巴拉多利德", ("Real Valladolid",), 41.644, -4.761, "José Zorrilla"),
    TeamInfo("Cadiz", "加的斯", ("Cádiz", "Cadiz CF"), 36.503, -6.273, "Nuevo Mirandilla"),
    TeamInfo("Granada", "格拉纳达", ("Granada CF",), 37.153, -3.596, "Nuevo Los Cármenes"),
    TeamInfo("Almeria", "阿尔梅里亚", ("Almería", "UD Almeria"), 36.840, -2.436, "Power Horse Stadium"),
    TeamInfo("Oviedo", "皇家奥维耶多", ("Real Oviedo",), 43.361, -5.870, "Carlos Tartiere"),
    TeamInfo("Eibar", "埃瓦尔", ("SD Eibar",), 43.182, -2.476, "Ipurua"),
    TeamInfo("Sporting Gijon", "希洪竞技", ("Sp Gijon", "Sporting Gijón"), 43.542, -5.637, "El Molinón"),
    TeamInfo("Zaragoza", "萨拉戈萨", ("Real Zaragoza",), 41.637, -0.902, "La Romareda"),
    # —— 德甲 / 德乙 ——
    TeamInfo("Union Berlin", "柏林联合", ("1. FC Union Berlin", "FC Union Berlin", "FCU"), 52.457, 13.568, "Stadion An der Alten Försterei"),
    TeamInfo("Bayer Leverkusen", "勒沃库森", ("Leverkusen", "Bayer 04", "B04"), 51.038, 7.002, "BayArena"),
    TeamInfo("Bayern Munich", "拜仁慕尼黑", ("Bayern", "FC Bayern", "Munich", "MUN", "拜仁"), 48.219, 11.625, "Allianz Arena"),
    TeamInfo("Borussia Dortmund", "多特蒙德", ("Dortmund", "BVB", "DOR", "多特"), 51.493, 7.452, "Signal Iduna Park"),
    TeamInfo("Borussia Monchengladbach", "门兴格拉德巴赫", ("M'gladbach", "Gladbach", "Monchengladbach", "Mönchengladbach", "BMG"), 51.175, 6.385, "Borussia-Park"),
    TeamInfo("Eintracht Frankfurt", "法兰克福", ("Ein Frankfurt", "Frankfurt", "SGE"), 50.069, 8.645, "Deutsche Bank Park"),
    TeamInfo("Augsburg", "奥格斯堡", ("FC Augsburg", "FCA"), 48.323, 10.884, "WWK Arena"),
    TeamInfo("FC Cologne", "科隆", ("FC Koln", "Koln", "Köln", "Cologne", "KOE"), 50.934, 6.875, "RheinEnergieStadion"),
    TeamInfo("Hamburg", "汉堡", ("Hamburg SV", "HSV", "Hamburger SV"), 53.587, 9.899, "Volksparkstadion"),
    TeamInfo("Mainz", "美因茨", ("Mainz 05", "FSV Mainz", "M05"), 49.984, 8.224, "MEWA Arena"),
    TeamInfo("RB Leipzig", "莱比锡红牛", ("Leipzig", "RBL"), 51.346, 12.348, "Red Bull Arena"),
    TeamInfo("Freiburg", "弗赖堡", ("SC Freiburg", "SCF"), 47.989, 7.893, "Europa-Park Stadion"),
    TeamInfo("Paderborn", "帕德博恩", ("SC Paderborn 07", "Paderborn 07", "SCP"), 51.731, 8.711, "Home Deluxe Arena"),
    TeamInfo("Elversberg", "埃尔弗斯贝格", ("SV Elversberg", "ELV"), 49.319, 7.124, "URSAPHARM-Arena"),
    TeamInfo("Schalke 04", "沙尔克04", ("Schalke", "S04"), 51.555, 7.068, "Veltins-Arena"),
    TeamInfo("Hoffenheim", "霍芬海姆", ("TSG Hoffenheim", "TSG"), 49.239, 8.888, "PreZero Arena"),
    TeamInfo("Stuttgart", "斯图加特", ("VfB Stuttgart", "VFB"), 48.792, 9.232, "MHPArena"),
    TeamInfo("Werder Bremen", "云达不莱梅", ("Werder", "Bremen", "SVW"), 53.067, 8.838, "Weserstadion"),
    TeamInfo("Wolfsburg", "沃尔夫斯堡", ("VfL Wolfsburg",), 52.432, 10.804, "Volkswagen Arena"),
    TeamInfo("Heidenheim", "海登海姆", ("FC Heidenheim", "1. FC Heidenheim"), 48.668, 10.139, "Voith-Arena"),
    TeamInfo("St Pauli", "圣保利", ("FC St. Pauli", "St. Pauli"), 53.555, 9.968, "Millerntor-Stadion"),
    TeamInfo("Holstein Kiel", "基尔", ("Kiel",), 54.349, 10.124, "Holstein-Stadion"),
    TeamInfo("Bochum", "波鸿", ("VfL Bochum",), 51.490, 7.237, "Vonovia Ruhrstadion"),
    TeamInfo("Darmstadt", "达姆施塔特", ("Darmstadt 98",), 49.858, 8.669, "Merck-Stadion am Böllenfalltor"),
    TeamInfo("Union Berlin", "柏林联合", ("1. FC Union Berlin",), 52.457, 13.568, "Stadion An der Alten Försterei"),
    TeamInfo("Hertha", "柏林赫塔", ("Hertha Berlin", "Hertha BSC"), 52.515, 13.239, "Olympiastadion Berlin"),
    TeamInfo("Hannover", "汉诺威96", ("Hannover 96",), 52.360, 9.731, "Heinz von Heiden Arena"),
    TeamInfo("Nurnberg", "纽伦堡", ("Nürnberg", "FC Nurnberg"), 49.427, 11.126, "Max-Morlock-Stadion"),
    TeamInfo("Greuther Furth", "菲尔特", ("Greuther Fürth",), 49.487, 10.999, "Sportpark Ronhof"),
    TeamInfo("Kaiserslautern", "凯泽斯劳滕", ("1. FC Kaiserslautern",), 49.435, 7.776, "Fritz-Walter-Stadion"),
    TeamInfo("Fortuna Dusseldorf", "杜塞尔多夫", ("Fortuna Düsseldorf", "Dusseldorf"), 51.262, 6.733, "Merkur Spiel-Arena"),
    # —— 意甲 / 意乙 ——
    TeamInfo("AC Milan", "AC米兰", ("Milan", "MIL", "米兰"), 45.478, 9.124, "San Siro"),
    TeamInfo("AS Roma", "罗马", ("Roma", "ROMA"), 41.934, 12.455, "Stadio Olimpico"),
    TeamInfo("Atalanta", "亚特兰大", ("Atalanta BC", "ATA"), 45.709, 9.681, "Gewiss Stadium"),
    TeamInfo("Bologna", "博洛尼亚", ("Bologna FC", "BOL"), 44.492, 11.310, "Renato Dall'Ara"),
    TeamInfo("Cagliari", "卡利亚里", ("Cagliari Calcio", "CAG"), 39.200, 9.138, "Unipol Domus"),
    TeamInfo("Como", "科莫", ("Como 1907", "COMO"), 45.814, 9.072, "Giuseppe Sinigaglia"),
    TeamInfo("Fiorentina", "佛罗伦萨", ("ACF Fiorentina", "FIO"), 43.781, 11.282, "Artemio Franchi"),
    TeamInfo("Frosinone", "弗洛西诺内", ("Frosinone Calcio", "FRO"), 41.635, 13.322, "Benito Stirpe"),
    TeamInfo("Genoa", "热那亚", ("Genoa CFC", "GEN"), 44.416, 8.952, "Luigi Ferraris"),
    TeamInfo("Internazionale", "国际米兰", ("Inter", "Inter Milan", "FC Internazionale", "INT", "国米"), 45.478, 9.124, "San Siro"),
    TeamInfo("Juventus", "尤文图斯", ("Juve", "JUV", "尤文"), 45.110, 7.641, "Allianz Stadium"),
    TeamInfo("Lazio", "拉齐奥", ("SS Lazio", "LAZ"), 41.934, 12.455, "Stadio Olimpico"),
    TeamInfo("Lecce", "莱切", ("US Lecce", "LEC"), 40.365, 18.209, "Via del Mare"),
    TeamInfo("Monza", "蒙扎", ("AC Monza", "MON"), 45.583, 9.308, "U-Power Stadium"),
    TeamInfo("Napoli", "那不勒斯", ("SSC Napoli", "NAP"), 40.828, 14.193, "Diego Armando Maradona"),
    TeamInfo("Parma", "帕尔马", ("Parma Calcio", "PAR"), 44.795, 10.338, "Ennio Tardini"),
    TeamInfo("Sassuolo", "萨索洛", ("US Sassuolo", "SAS"), 44.525, 10.766, "Mapei Stadium"),
    TeamInfo("Torino", "都灵", ("Torino FC", "TOR"), 45.042, 7.650, "Olimpico Grande Torino"),
    TeamInfo("Udinese", "乌迪内斯", ("Udinese Calcio", "UDI"), 46.082, 13.200, "Bluenergy Stadium"),
    TeamInfo("Venezia", "威尼斯", ("Venezia FC", "VEN"), 45.428, 12.364, "Pier Luigi Penzo"),
    TeamInfo("Verona", "维罗纳", ("Hellas Verona",), 45.435, 10.969, "Marcantonio Bentegodi"),
    TeamInfo("Empoli", "恩波利", ("Empoli FC",), 43.726, 10.955, "Carlo Castellani"),
    TeamInfo("Salernitana", "萨勒尼塔纳", ("US Salernitana",), 40.645, 14.824, "Arechi"),
    TeamInfo("Spezia", "斯佩齐亚", ("Spezia Calcio",), 44.102, 9.808, "Alberto Picco"),
    TeamInfo("Cremonese", "克雷莫纳", ("US Cremonese",), 45.140, 10.031, "Giovanni Zini"),
    TeamInfo("Pisa", "比萨", ("AC Pisa", "Pisa SC"), 43.725, 10.401, "Arena Garibaldi"),
    TeamInfo("Palermo", "巴勒莫", ("Palermo FC",), 38.153, 13.342, "Renzo Barbera"),
    TeamInfo("Sampdoria", "桑普多利亚", ("UC Sampdoria",), 44.416, 8.952, "Luigi Ferraris"),
    TeamInfo("Bari", "巴里", ("SSC Bari",), 41.085, 16.840, "San Nicola"),
)

# 后写入覆盖同名（上面 Union Berlin 写了两次，构建映射时后者覆盖，无妨）
_ALIAS_MAP: dict[str, TeamInfo] = {}
_CANONICAL: dict[str, TeamInfo] = {}
for _info in TEAMS:
    _CANONICAL[normalize_name(_info.canonical)] = _info
    _CANONICAL[normalize_name(_info.name_cn)] = _info
    for _alias in (_info.canonical, _info.name_cn) + _info.aliases:
        _ALIAS_MAP[normalize_name(_alias)] = _info


def resolve_team(name: str) -> TeamInfo | None:
    if not name:
        return None
    key = normalize_name(name)
    if key in _ALIAS_MAP:
        return _ALIAS_MAP[key]
    # 子串 / 模糊
    best: TeamInfo | None = None
    best_score = 0
    for alias, info in _ALIAS_MAP.items():
        if not alias:
            continue
        if alias in key or key in alias:
            score = min(len(alias), len(key))
            if score > best_score:
                best, best_score = info, score
    if best and best_score >= 4:
        return best
    return None


def display_cn(name: str) -> str:
    info = resolve_team(name)
    return info.name_cn if info else name


def canonical_name(name: str) -> str:
    info = resolve_team(name)
    return info.canonical if info else name


def stadium_coords(name: str) -> tuple[float, float, str] | None:
    info = resolve_team(name)
    if not info:
        return None
    return info.lat, info.lon, info.stadium


def team_keywords(name: str) -> list[str]:
    info = resolve_team(name)
    if not info:
        return [name]
    keys = [info.canonical, info.name_cn, *info.aliases]
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        k = key.strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out


def all_team_infos() -> list[TeamInfo]:
    seen: dict[str, TeamInfo] = {}
    for info in TEAMS:
        seen[info.canonical] = info
    return list(seen.values())


def all_canonical_names() -> list[str]:
    return sorted(info.canonical for info in all_team_infos())
