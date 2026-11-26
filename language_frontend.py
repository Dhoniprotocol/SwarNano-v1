import re
import unicodedata

try:
    import cmudict
except ImportError:
    cmudict = None


LANGUAGES = [
    ("ne", "Nepali"),
    ("hi", "Hindi"),
    ("sa", "Sanskrit"),
    ("mr", "Marathi"),
    ("kok", "Konkani"),
    ("mai", "Maithili"),
    ("bho", "Bhojpuri"),
    ("en", "English (Latin or phonetic Devanagari)"),
    ("ja", "Japanese (Romaji or Devanagari)"),
    ("sw", "Swahili"),
    ("id", "Indonesian"),
    ("ms", "Malay"),
    ("es", "Spanish"),
    ("it", "Italian"),
    ("de", "German"),
    ("nl", "Dutch"),
    ("bn", "Bengali"),
    ("gu", "Gujarati"),
    ("pa", "Punjabi (Gurmukhi)"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("kn", "Kannada"),
    ("si", "Sinhala"),
    ("fr", "French"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("tr", "Turkish"),
    ("ha", "Hausa"),
    ("yo", "Yoruba (Latin)"),
    ("so", "Somali"),
    ("zh", "Mandarin (Pinyin; tone marks approximate)"),
    ("bo", "Tibetan (Wylie-style Latin)"),
    ("ur", "Urdu (Arabic script or Roman Urdu)"),
    ("ar", "Arabic (Arabic script or Romanized)"),
    ("fa", "Persian (Arabic script or Romanized)"),
    ("he", "Hebrew (Latin transliteration)"),
    ("ko", "Korean (Hangul or Revised Romanization)"),
]

LANGUAGE_CODES = {code for code, _ in LANGUAGES}
DEVANAGARI_LANGUAGES = {"ne", "hi", "sa", "mr", "kok", "mai", "bho"}

_SCRIPT_MAPS = {
    "bn": {
        "অ": "अ", "আ": "आ", "ই": "इ", "ঈ": "ई", "উ": "उ", "ঊ": "ऊ", "ঋ": "ऋ",
        "এ": "ए", "ঐ": "ऐ", "ও": "ओ", "ঔ": "औ", "া": "ा", "ি": "ि", "ী": "ी",
        "ু": "ु", "ূ": "ू", "ৃ": "ृ", "ে": "े", "ৈ": "ै", "ো": "ो", "ৌ": "ौ",
        "ক": "क", "খ": "ख", "গ": "ग", "ঘ": "घ", "ঙ": "ङ", "চ": "च", "ছ": "छ",
        "জ": "ज", "ঝ": "झ", "ঞ": "ञ", "ট": "ट", "ঠ": "ठ", "ড": "ड", "ঢ": "ढ",
        "ণ": "ण", "ত": "त", "থ": "थ", "দ": "द", "ধ": "ध", "ন": "न", "প": "प",
        "ফ": "फ", "ব": "ब", "ভ": "भ", "ম": "म", "য": "य", "য়": "य", "র": "र",
        "ল": "ल", "শ": "श", "ষ": "ष", "স": "स", "হ": "ह", "ং": "ं", "ঁ": "ँ",
        "ঃ": "ः", "্": "्",
    },
    "gu": {
        "અ": "अ", "આ": "आ", "ઇ": "इ", "ઈ": "ई", "ઉ": "उ", "ઊ": "ऊ", "ઋ": "ऋ",
        "એ": "ए", "ઐ": "ऐ", "ઓ": "ओ", "ઔ": "औ", "ા": "ा", "િ": "ि", "ી": "ी",
        "ુ": "ु", "ૂ": "ू", "ૃ": "ृ", "ે": "े", "ૈ": "ै", "ો": "ो", "ૌ": "ौ",
        "ક": "क", "ખ": "ख", "ગ": "ग", "ઘ": "घ", "ઙ": "ङ", "ચ": "च", "છ": "छ",
        "જ": "ज", "ઝ": "झ", "ઞ": "ञ", "ટ": "ट", "ઠ": "ठ", "ડ": "ड", "ઢ": "ढ",
        "ણ": "ण", "ત": "त", "થ": "थ", "દ": "द", "ધ": "ध", "ન": "न", "પ": "प",
        "ફ": "फ", "બ": "ब", "ભ": "भ", "મ": "म", "ય": "य", "ર": "र", "લ": "ल",
        "વ": "व", "શ": "श", "ષ": "ष", "સ": "स", "હ": "ह", "ં": "ं", "ઃ": "ः",
        "્": "्",
    },
    "pa": {
        "ੳ": "अ", "ਅ": "अ", "ਆ": "आ", "ਇ": "इ", "ਈ": "ई", "ਉ": "उ", "ਊ": "ऊ",
        "ਏ": "ए", "ਐ": "ऐ", "ਓ": "ओ", "ਔ": "औ", "ਾ": "ा", "ਿ": "ि", "ੀ": "ी",
        "ੁ": "ु", "ੂ": "ू", "ੇ": "े", "ੈ": "ै", "ੋ": "ो", "ੌ": "ौ",
        "ਕ": "क", "ਖ": "ख", "ਗ": "ग", "ਘ": "घ", "ਙ": "ङ", "ਚ": "च", "ਛ": "छ",
        "ਜ": "ज", "ਝ": "झ", "ਞ": "ञ", "ਟ": "ट", "ਠ": "ठ", "ਡ": "ड", "ਢ": "ढ",
        "ਣ": "ण", "ਤ": "त", "ਥ": "थ", "ਦ": "द", "ਧ": "ध", "ਨ": "न", "ਪ": "प",
        "ਫ": "फ", "ਬ": "ब", "ਭ": "भ", "ਮ": "म", "ਯ": "य", "ਰ": "र", "ਲ": "ल",
        "ਵ": "व", "ੜ": "ड़", "ਸ": "स", "ਹ": "ह", "ਂ": "ं", "ੰ": "ं", "ੱ": "्",
        "੍": "्",
    },
    "ta": {
        "அ": "अ", "ஆ": "आ", "இ": "इ", "ஈ": "ई", "உ": "उ", "ஊ": "ऊ", "எ": "ए",
        "ஏ": "ए", "ஐ": "ऐ", "ஒ": "ओ", "ஓ": "ओ", "ஔ": "औ", "ா": "ा", "ி": "ि",
        "ீ": "ी", "ு": "ु", "ூ": "ू", "ெ": "े", "ே": "े", "ை": "ै", "ொ": "ो",
        "ோ": "ो", "ௌ": "ौ", "்": "्", "க": "क", "ங": "ङ", "ச": "च", "ஞ": "ञ",
        "ட": "ट", "ண": "ण", "த": "त", "ந": "न", "ன": "न", "ப": "प", "ம": "म",
        "ய": "य", "ர": "र", "ற": "र", "ல": "ल", "ள": "ळ", "ழ": "ळ", "வ": "व",
        "ஶ": "श", "ஷ": "ष", "ஸ": "स", "ஹ": "ह", "ஃ": "ह",
    },
    "te": {
        "అ": "अ", "ఆ": "आ", "ఇ": "इ", "ఈ": "ई", "ఉ": "उ", "ఊ": "ऊ", "ఋ": "ऋ",
        "ఎ": "ए", "ఏ": "ए", "ఐ": "ऐ", "ఒ": "ओ", "ఓ": "ओ", "ఔ": "औ", "ా": "ा",
        "ి": "ि", "ీ": "ी", "ు": "ु", "ూ": "ू", "ృ": "ृ", "ె": "े", "ే": "े",
        "ై": "ै", "ొ": "ो", "ో": "ो", "ౌ": "ौ", "్": "्", "క": "क", "ఖ": "ख",
        "గ": "ग", "ఘ": "घ", "ఙ": "ङ", "చ": "च", "ఛ": "छ", "జ": "ज", "ఝ": "झ",
        "ఞ": "ञ", "ట": "ट", "ఠ": "ठ", "డ": "ड", "ఢ": "ढ", "ణ": "ण", "త": "त",
        "థ": "थ", "ద": "द", "ధ": "ध", "న": "न", "ప": "प", "ఫ": "फ", "బ": "ब",
        "భ": "भ", "మ": "म", "య": "य", "ర": "र", "ల": "ल", "వ": "व", "శ": "श",
        "ష": "ष", "స": "स", "హ": "ह", "ం": "ं", "ః": "ः",
    },
    "kn": {
        "ಅ": "अ", "ಆ": "आ", "ಇ": "इ", "ಈ": "ई", "ಉ": "उ", "ಊ": "ऊ", "ಋ": "ऋ",
        "ಎ": "ए", "ಏ": "ए", "ಐ": "ऐ", "ಒ": "ओ", "ಓ": "ओ", "ಔ": "औ", "ಾ": "ा",
        "ಿ": "ि", "ೀ": "ी", "ು": "ु", "ೂ": "ू", "ೃ": "ृ", "ೆ": "े", "ೇ": "े",
        "ೈ": "ै", "ೊ": "ो", "ೋ": "ो", "ೌ": "ौ", "್": "्", "ಕ": "क", "ಖ": "ख",
        "ಗ": "ग", "ಘ": "घ", "ಙ": "ङ", "ಚ": "च", "ಛ": "छ", "ಜ": "ज", "ಝ": "झ",
        "ಞ": "ञ", "ಟ": "ट", "ಠ": "ठ", "ಡ": "ड", "ಢ": "ढ", "ಣ": "ण", "ತ": "त",
        "ಥ": "थ", "ದ": "द", "ಧ": "ध", "ನ": "न", "ಪ": "प", "ಫ": "फ", "ಬ": "ब",
        "ಭ": "भ", "ಮ": "म", "ಯ": "य", "ರ": "र", "ಲ": "ल", "ವ": "व", "ಶ": "श",
        "ಷ": "ष", "ಸ": "स", "ಹ": "ह", "ಂ": "ं", "ಃ": "ः",
    },
    "si": {
        "අ": "अ", "ආ": "आ", "ඇ": "ए", "ඈ": "ए", "ඉ": "इ", "ඊ": "ई", "උ": "उ",
        "ඌ": "ऊ", "එ": "ए", "ඒ": "ए", "ඓ": "ऐ", "ඔ": "ओ", "ඕ": "ओ", "ඖ": "औ",
        "ා": "ा", "ැ": "े", "ෑ": "े", "ි": "ि", "ී": "ी", "ු": "ु", "ූ": "ू",
        "ෙ": "े", "ේ": "े", "ො": "ो", "ෝ": "ो", "ෞ": "ौ", "්": "्", "ක": "क",
        "ඛ": "ख", "ග": "ग", "ඝ": "घ", "ඞ": "ङ", "ච": "च", "ඡ": "छ", "ජ": "ज",
        "ඣ": "झ", "ඤ": "ञ", "ට": "ट", "ඨ": "ठ", "ඩ": "ड", "ඪ": "ढ", "ණ": "ण",
        "ත": "त", "ථ": "थ", "ද": "द", "ධ": "ध", "න": "न", "ප": "प", "ඵ": "फ",
        "බ": "ब", "භ": "भ", "ම": "म", "ය": "य", "ර": "र", "ල": "ल", "ව": "व",
        "ශ": "श", "ෂ": "ष", "ස": "स", "හ": "ह", "ං": "ं", "ඃ": "ः",
    },
}

_LATIN_COMMON = {
    "aa": ("V", "आ"), "ee": ("V", "ई"), "ii": ("V", "ई"), "oo": ("V", "ऊ"),
    "ou": ("V", "औ"), "au": ("V", "औ"), "ai": ("V", "ऐ"), "ay": ("V", "ए"),
    "ei": ("V", "ए"), "ey": ("V", "ए"), "oi": ("V", "ओइ"), "oy": ("V", "ओइ"),
    "ao": ("V", "आओ"),
    "kh": ("C", "ख"), "gh": ("C", "घ"), "ch": ("C", "च"), "sh": ("C", "श"),
    "th": ("C", "थ"), "dh": ("C", "ध"), "ph": ("C", "फ"), "bh": ("C", "भ"),
    "jh": ("C", "झ"), "ng": ("C", "ङ"), "ny": ("C", "ञ"), "zh": ("C", "झ"),
    "ts": ("C", "त्स"), "dz": ("C", "ज"), "qu": ("C", "क्व"), "ck": ("C", "क"),
    "x": ("C", "क्स"), "a": ("V", "अ"), "e": ("V", "ए"), "i": ("V", "इ"),
    "o": ("V", "ओ"), "u": ("V", "उ"), "y": ("C", "य"), "b": ("C", "ब"),
    "c": ("C", "क"), "d": ("C", "द"), "f": ("C", "फ"), "g": ("C", "ग"),
    "h": ("C", "ह"), "j": ("C", "ज"), "k": ("C", "क"), "l": ("C", "ल"),
    "m": ("C", "म"), "n": ("C", "न"), "p": ("C", "प"), "q": ("C", "क"),
    "r": ("C", "र"), "s": ("C", "स"), "t": ("C", "त"), "v": ("C", "व"),
    "w": ("C", "व"), "z": ("C", "ज"),
}

_LANGUAGE_RULES = {
    "en": {"tion": [("C", "श"), ("V", "अ"), ("C", "न")], "igh": [("V", "आइ")], "oo": [("V", "ऊ")], "ea": [("V", "ई")], "ow": [("V", "आउ")]},
    "es": {"ll": [("C", "य")], "ñ": [("C", "ञ")], "j": [("C", "ह")], "h": [], "qu": [("C", "क")], "rr": [("C", "र"), ("C", "र")]},
    "it": {"gli": [("C", "ल्य")], "gn": [("C", "ञ")], "ch": [("C", "क")], "gh": [("C", "ग")], "ci": [("C", "च"), ("V", "इ")], "gi": [("C", "ज"), ("V", "इ")]},
    "fr": {"eau": [("V", "ओ")], "ou": [("V", "उ")], "oi": [("V", "वा")], "ch": [("C", "श")], "gn": [("C", "ञ")], "ph": [("C", "फ")], "on": [("V", "ओँ")], "an": [("V", "आँ")], "en": [("V", "आँ")], "in": [("V", "एँ")], "ç": [("C", "स")], "h": []},
    "de": {"sch": [("C", "श")], "ch": [("C", "ख")], "ei": [("V", "आइ")], "ie": [("V", "ई")], "eu": [("V", "ऑय")], "ä": [("V", "ए")], "ö": [("V", "ओ")], "ü": [("V", "उ")], "ß": [("C", "स"), ("C", "स")]},
    "nl": {"ij": [("V", "ऐ")], "oe": [("V", "ऊ")], "ui": [("V", "औइ")], "sch": [("C", "स"), ("C", "ख")]},
    "pt": {"lh": [("C", "ल्य")], "nh": [("C", "ञ")], "ão": [("V", "आँउ")], "ões": [("V", "ओइँ"), ("C", "स")], "ç": [("C", "स")], "ch": [("C", "श")], "j": [("C", "झ")], "rr": [("C", "ह")]},
    "tr": {"ş": [("C", "श")], "ç": [("C", "च")], "c": [("C", "ज")], "ğ": [], "ı": [("V", "अ")], "ö": [("V", "ओ")], "ü": [("V", "उ")]},
    "sw": {"ng'": [("C", "ङ")], "ch": [("C", "च")], "sh": [("C", "श")], "dh": [("C", "ध")], "th": [("C", "थ")]},
    "id": {"ng": [("C", "ङ")], "ny": [("C", "ञ")], "sy": [("C", "श")], "c": [("C", "च")]},
    "ms": {"ng": [("C", "ङ")], "ny": [("C", "ञ")], "sy": [("C", "श")], "c": [("C", "च")]},
    "ha": {"sh": [("C", "श")], "ts": [("C", "त्स")], "ƙ": [("C", "क")], "ɓ": [("C", "ब")], "ɗ": [("C", "द")]},
    "yo": {"ṣ": [("C", "श")], "ẹ": [("V", "ए")], "ọ": [("V", "ओ")], "ạ": [("V", "अ")], "gb": [("C", "ग"), ("C", "ब")]},
    "so": {"sh": [("C", "श")], "kh": [("C", "ख")], "dh": [("C", "ध")], "c": [("C", "च")]},
    "zh": {"zh": [("C", "झ")], "ch": [("C", "च")], "sh": [("C", "श")], "q": [("C", "च")], "x": [("C", "श")], "c": [("C", "त्स")], "z": [("C", "ज")], "ü": [("V", "यू")]},
    "bo": {"tsh": [("C", "छ")], "kh": [("C", "ख")], "ph": [("C", "फ")], "ng": [("C", "ङ")], "zh": [("C", "झ")], "sh": [("C", "श")]},
    "ur": {"kh": [("C", "ख")], "gh": [("C", "ग़")], "sh": [("C", "श")], "ch": [("C", "च")], "zh": [("C", "झ")], "aa": [("V", "आ")], "ee": [("V", "ई")], "oo": [("V", "ऊ")]},
    "ar": {"kh": [("C", "ख")], "gh": [("C", "ग़")], "sh": [("C", "श")], "th": [("C", "थ")], "dh": [("C", "ध")], "aa": [("V", "आ")]},
    "fa": {"kh": [("C", "ख")], "gh": [("C", "ग़")], "sh": [("C", "श")], "zh": [("C", "झ")], "ch": [("C", "च")], "aa": [("V", "आ")]},
    "he": {"sh": [("C", "श")], "ch": [("C", "ख")], "ts": [("C", "त्स")], "kh": [("C", "ख")]},
}

_CMU_CONSONANTS = {
    "B": "ब", "CH": "च", "D": "द", "DH": "द", "F": "फ", "G": "ग",
    "HH": "ह", "JH": "ज", "K": "क", "L": "ल", "M": "म", "N": "न",
    "NG": "ङ", "P": "प", "R": "र", "S": "स", "SH": "श", "T": "त",
    "TH": "थ", "V": "व", "W": "व", "Y": "य", "Z": "ज", "ZH": "झ",
    "EL": "ल", "EM": "म", "EN": "न",
}
_CMU_VOWELS = {
    "AA": "आ", "AE": "ऐ", "AH": "अ", "AO": "ओ", "AW": "औ", "AY": "आइ",
    "EH": "ए", "EY": "ए", "IH": "इ", "IY": "ई", "OW": "ओ", "OY": "ओइ",
    "UH": "उ", "UW": "ऊ", "AX": "अ", "IX": "इ",
}

_CMU_PRONUNCIATIONS = cmudict.dict() if cmudict is not None else {}

_JAPANESE_MORA = {
    "kya": "क्य", "kyu": "क्यु", "kyo": "क्यो", "sha": "शा", "shu": "शु", "sho": "शो",
    "cha": "चा", "chu": "चु", "cho": "चो", "nya": "ञा", "nyu": "ञु", "nyo": "ञो",
    "ja": "जा", "ju": "जु", "jo": "जो", "shi": "शि", "chi": "चि", "tsu": "त्सु",
    "fu": "फु", "ji": "जि", "ka": "का", "ki": "कि", "ku": "कु", "ke": "के", "ko": "को",
    "sa": "सा", "si": "सि", "su": "सु", "se": "से", "so": "सो", "ta": "ता", "ti": "ति",
    "te": "ते", "to": "तो", "na": "ना", "ni": "नि", "nu": "नु", "ne": "ने", "no": "नो",
    "ha": "हा", "hi": "हि", "he": "हे", "ho": "हो", "ma": "मा", "mi": "मि", "mu": "मु",
    "me": "मे", "mo": "मो", "ya": "या", "yu": "यु", "yo": "यो", "ra": "रा", "ri": "रि",
    "ru": "रु", "re": "रे", "ro": "रो", "wa": "वा", "wi": "वि", "we": "वे", "wo": "ओ",
    "a": "अ", "i": "इ", "u": "उ", "e": "ए", "o": "ओ",
}

_RUSSIAN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "ye", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ы": "i", "э": "e", "ю": "yu", "я": "ya", "ъ": "", "ь": "",
}

_URDU_ARABIC = {
    "ا": "आ", "آ": "आ", "ب": "ब", "پ": "प", "ت": "त", "ٹ": "ट", "ث": "स",
    "ج": "ज", "چ": "च", "ح": "ह", "خ": "ख", "د": "द", "ڈ": "ड", "ذ": "ज",
    "ر": "र", "ڑ": "ड़", "ز": "ज", "ژ": "झ", "س": "स", "ش": "श", "ص": "स",
    "ض": "ज", "ط": "त", "ظ": "ज", "ع": "अ", "غ": "ग़", "ف": "फ", "ق": "क",
    "ک": "क", "گ": "ग", "ل": "ल", "م": "म", "ن": "न", "ں": "ँ", "و": "व",
    "ہ": "ह", "ھ": "ह", "ء": "", "ی": "य", "ے": "े", "ؤ": "ओ", "ئ": "इ",
    "َ": "ा", "ِ": "ि", "ُ": "ु", "ّ": "्", "ْ": "्", "ً": "ं", "ٌ": "ुं",
    "ٍ": "िं", "۔": "।", "؟": "?", "،": ",",
}

_ARABIC = dict(_URDU_ARABIC, **{
    "ة": "त", "ك": "क", "ي": "य", "ى": "आ", "ء": "", "ؤ": "उ", "ئ": "इ",
})

_DEVANAGARI_RANGES = ((0x0900, 0x097F), (0xA8E0, 0xA8FF))


def _contains_devanagari(text):
    return any(any(start <= ord(char) <= end for start, end in _DEVANAGARI_RANGES) for char in text)


def _indic_script(text, language):
    mapping = _SCRIPT_MAPS[language]
    return "".join(mapping.get(char, char) for char in text)


def _compose_latin_word(word, language):
    rules = dict(_LATIN_COMMON)
    rules.update(_LANGUAGE_RULES.get(language, {}))
    keys = sorted(rules, key=len, reverse=True)
    tokens = []
    i = 0
    while i < len(word):
        matched = next((key for key in keys if word.startswith(key, i)), None)
        if matched is None:
            char = word[i]
            if char.isdigit():
                i += 1
                continue
            return None
        token = rules[matched]
        if isinstance(token, tuple):
            tokens.append(token)
        else:
            tokens.extend(token)
        i += len(matched)

    output = []
    onset = []
    for kind, glyph in tokens:
        if kind == "C":
            onset.extend(glyph)
            continue
        vowel_parts = list(glyph)
        for consonant in onset[:-1]:
            output.append(consonant + "्")
        vowel = "".join(vowel_parts)
        if onset:
            output.append(onset[-1] + _vowel_sign(vowel))
        else:
            output.append(vowel)
        onset = []
    if onset:
        output.extend(consonant + "्" for consonant in onset)
    return "".join(output)


def _vowel_sign(vowel):
    if len(vowel) > 1:
        return _vowel_sign(vowel[0]) + vowel[1:]
    return {
        "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
        "ऋ": "ृ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
    }.get(vowel, "्" + vowel)


def _latin_text(text, language):
    if language == "en":
        return _english_text(text)
    if language == "ru":
        text = "".join(_RUSSIAN.get(char, char) for char in text.lower())
    if language == "ja":
        return _romaji_text(text)
    text = _normalize_latin(text, language)
    words = re.findall(r"[^\W_]+|[^\w\s]+|\s+", text, flags=re.UNICODE)
    output = []
    for word in words:
        if word.isspace() or not any(char.isalpha() for char in word):
            output.append(word)
            continue
        rendered = _compose_latin_word(word, language)
        if rendered is None:
            raise ValueError(f"Cannot transliterate {word!r} for {dict(LANGUAGES).get(language, language)}. Enter a pronunciation spelling in Devanagari or Latin.")
        output.append(rendered)
    return "".join(output)


def _cmu_to_devanagari(phones):
    output = []
    onset = []

    def finish_onset(vowel=None):
        nonlocal onset
        if not onset:
            return vowel or ""
        if vowel is None:
            rendered = "".join(consonant + "्" for consonant in onset)
            onset = []
            return rendered
        rendered = "".join(consonant + "्" for consonant in onset[:-1])
        rendered += onset[-1] + _vowel_sign(vowel)
        onset = []
        return rendered

    for phone in phones:
        phone = re.sub(r"\d+$", "", phone)
        if phone in _CMU_CONSONANTS:
            onset.append(_CMU_CONSONANTS[phone])
        elif phone in _CMU_VOWELS:
            output.append(finish_onset(_CMU_VOWELS[phone]))
        elif phone in {"ER", "AXR"}:
            if onset:
                output.append(finish_onset("अ"))
                onset.append("र")
            else:
                output.append("अर")
        else:
            return None
    if onset:
        output.append(finish_onset())
    return "".join(output)


def _english_text(text):
    if not _CMU_PRONUNCIATIONS:
        raise ValueError("English pronunciation data is unavailable. Install it with: python -m pip install -r requirements-pronunciation.txt")
    text = _normalize_latin(text, "en").replace("’", "'")
    pieces = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|[^A-Za-z]+", text)
    output = []
    for piece in pieces:
        if not piece or not piece[0].isalpha():
            output.append(piece)
            continue
        pronunciations = _CMU_PRONUNCIATIONS.get(piece.lower())
        if pronunciations:
            rendered = _cmu_to_devanagari(pronunciations[0])
            if rendered is not None:
                output.append(rendered)
                continue
        suffix_match = re.fullmatch(r"([a-z]+)'(s|re|ve|ll|d|m)", piece.lower())
        if suffix_match:
            base, suffix = suffix_match.groups()
            base_pronunciations = _CMU_PRONUNCIATIONS.get(base)
            if base_pronunciations:
                phones = list(base_pronunciations[0])
                final_phone = re.sub(r"\d+$", "", phones[-1]) if phones else ""
                if suffix == "s":
                    if final_phone in {"S", "Z", "SH", "ZH", "CH", "JH"}:
                        suffix_phones = ["IH", "Z"]
                    elif final_phone in {"P", "T", "K", "F", "TH"}:
                        suffix_phones = ["S"]
                    else:
                        suffix_phones = ["Z"]
                else:
                    suffix_phones = {
                        "re": ["ER"],
                        "ve": ["V"],
                        "ll": ["L"],
                        "d": ["D"],
                        "m": ["M"],
                    }[suffix]
                output.append(_cmu_to_devanagari(phones + suffix_phones))
                continue
            rendered_base = _compose_latin_word(base, "en")
            if rendered_base is not None:
                suffix_phone = "Z" if suffix == "s" else {
                    "re": "ER",
                    "ve": "V",
                    "ll": "L",
                    "d": "D",
                    "m": "M",
                }[suffix]
                output.append(rendered_base + _cmu_to_devanagari([suffix_phone]))
                continue
        fallback = _compose_latin_word(piece, "en")
        if fallback is None:
            raise ValueError(f"No English pronunciation found for {piece!r}; enter its pronunciation in Devanagari.")
        output.append(fallback)
    return "".join(output)


def _normalize_latin(text, language):
    keep = {
        "de": set("äöüß"),
        "es": set("ñ"),
        "pt": set("ãõç"),
        "fr": set("ç"),
        "tr": set("çğıöşü"),
        "zh": set("ü"),
    }.get(language, set())
    output = []
    for char in unicodedata.normalize("NFC", text).lower():
        if char in keep:
            output.append(char)
        else:
            output.extend(
                base for base in unicodedata.normalize("NFD", char)
                if not unicodedata.combining(base)
            )
    return "".join(output)


def _romaji_text(text):
    text = unicodedata.normalize("NFC", text).lower()
    mora = sorted(_JAPANESE_MORA, key=len, reverse=True)
    output = []
    for word in re.findall(r"[a-z']+|[^a-z]+", text):
        if not word or not word[0].isascii() or not word[0].isalpha():
            output.append(word)
            continue
        i = 0
        pieces = []
        while i < len(word):
            if word[i] == "n" and word[i + 1:i + 2] == "n":
                pieces.append("न्")
                i += 1
                continue
            if word[i] == "n" and (i + 1 == len(word) or word[i + 1] not in "aiueoy"):
                pieces.append("ं")
                i += 1
                continue
            if word[i] == word[i + 1:i + 2] and word[i] not in "aeioun":
                pieces.append("्")
                i += 1
                continue
            matched = next((key for key in mora if word.startswith(key, i)), None)
            if matched is None:
                raise ValueError(f"Cannot read Japanese Romaji near {word[i:]!r}. Use Hepburn-style Romaji or Devanagari pronunciation.")
            pieces.append(_JAPANESE_MORA[matched])
            i += len(matched)
        output.append("".join(pieces))
    return "".join(output)


def _hangul_to_roman(text):
    initials = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
    medials = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
    finals = ["", "k", "k", "ks", "n", "nj", "nh", "t", "l", "lk", "lm", "lb", "ls", "lt", "lp", "lh", "m", "p", "ps", "t", "t", "ng", "t", "t", "k", "t", "p", "t"]
    out = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            offset = code - 0xAC00
            initial = offset // 588
            medial = (offset % 588) // 28
            final = offset % 28
            out.append(initials[initial] + medials[medial] + finals[final])
        else:
            out.append(char)
    return "".join(out)


def to_devanagari(text, language):
    if language not in LANGUAGE_CODES:
        raise ValueError(f"Unsupported language code: {language}")
    text = unicodedata.normalize("NFC", text)
    has_non_devanagari_letters = any(
        char.isalpha() and not any(start <= ord(char) <= end for start, end in _DEVANAGARI_RANGES)
        for char in text
    )
    if _contains_devanagari(text) and not has_non_devanagari_letters:
        return text
    def convert_piece(piece):
        if not piece:
            return piece
        if _contains_devanagari(piece):
            return piece
        if language in _SCRIPT_MAPS and any(char in _SCRIPT_MAPS[language] for char in piece):
            return _indic_script(piece, language)
        if language == "ru" and any("\u0400" <= char <= "\u052F" for char in piece):
            return _latin_text(piece, "ru")
        if language in {"ur", "ar", "fa"} and any("\u0600" <= char <= "\u06FF" for char in piece):
            mapping = _URDU_ARABIC if language == "ur" else _ARABIC
            converted = "".join(mapping.get(char, char) for char in piece)
            if re.search(r"[\u0600-\u06FF]", converted):
                raise ValueError("Some Arabic-script characters are not mapped. Enter Romanized text or a Devanagari pronunciation spelling.")
            return converted
        if language == "ko" and any("\uAC00" <= char <= "\uD7A3" for char in piece):
            return _latin_text(_hangul_to_roman(piece), "ko")
        if language == "zh" and any("\u3400" <= char <= "\u9FFF" for char in piece):
            raise ValueError("For Mandarin, enter Pinyin (for example: Ni hao) or a Devanagari pronunciation spelling.")
        if language == "ja" and any("\u3040" <= char <= "\u30FF" for char in piece):
            raise ValueError("For Japanese, enter Hepburn-style Romaji (for example: Konnichiwa) or a Devanagari pronunciation spelling.")
        if any(char.isalpha() for char in piece):
            return _latin_text(piece, language)
        return piece

    parts = re.split(r"(\s+|[.!?।,;:]+)", text)
    return "".join(convert_piece(part) for part in parts)
