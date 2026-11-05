/* ===== البيانات الثابتة: الأطفال، المصحف، الخطة ===== */
const CHILDREN = {
  dalal: { id: 'dalal', name: 'دلال', age: 10, unit: 'page', unitLabel: 'صفحة' },
  farah: { id: 'farah', name: 'فرح', age: 8, unit: 'page', unitLabel: 'صفحة' },
  karim: { id: 'karim', name: 'كريم', age: 6, unit: 'lines', unitLabel: '4 أسطر' },
};
const CHILD_ORDER = ['dalal', 'farah', 'karim'];

const ROLES = {
  aya: { id: 'aya', name: 'آية', title: 'المعلمة الرئيسية', canColor: true, canDecide: true },
  asst: { id: 'asst', name: 'المساعدة', title: 'المعلمة المساعدة', canColor: false, canDecide: false },
  parent: { id: 'parent', name: 'ولي الأمر', title: 'ولي الأمر', canColor: false, canDecide: false, readOnly: true },
};

/* مصحف المدينة: 604 صفحات. بدايات الأجزاء والسور بالصفحة */
const JUZ_START = [1,22,42,62,82,102,121,142,162,182,201,222,242,262,282,302,322,342,362,382,402,422,442,462,482,502,522,542,562,582];
const SURAH_NAMES = ['الفاتحة','البقرة','آل عمران','النساء','المائدة','الأنعام','الأعراف','الأنفال','التوبة','يونس','هود','يوسف','الرعد','إبراهيم','الحجر','النحل','الإسراء','الكهف','مريم','طه','الأنبياء','الحج','المؤمنون','النور','الفرقان','الشعراء','النمل','القصص','العنكبوت','الروم','لقمان','السجدة','الأحزاب','سبأ','فاطر','يس','الصافات','ص','الزمر','غافر','فصلت','الشورى','الزخرف','الدخان','الجاثية','الأحقاف','محمد','الفتح','الحجرات','ق','الذاريات','الطور','النجم','القمر','الرحمن','الواقعة','الحديد','المجادلة','الحشر','الممتحنة','الصف','الجمعة','المنافقون','التغابن','الطلاق','التحريم','الملك','القلم','الحاقة','المعارج','نوح','الجن','المزمل','المدثر','القيامة','الإنسان','المرسلات','النبأ','النازعات','عبس','التكوير','الانفطار','المطففين','الانشقاق','البروج','الطارق','الأعلى','الغاشية','الفجر','البلد','الشمس','الليل','الضحى','الشرح','التين','العلق','القدر','البينة','الزلزلة','العاديات','القارعة','التكاثر','العصر','الهمزة','الفيل','قريش','الماعون','الكوثر','الكافرون','النصر','المسد','الإخلاص','الفلق','الناس'];
const SURAH_START = [1,2,50,77,106,128,151,177,187,208,221,235,249,255,262,267,282,293,305,312,322,332,342,350,359,367,377,385,396,404,411,415,418,428,434,440,446,453,458,467,477,483,489,496,499,502,507,511,515,518,520,523,526,528,531,534,537,542,545,549,551,553,554,556,558,560,562,564,566,568,570,572,574,575,577,578,580,582,583,585,586,587,587,589,590,591,591,592,593,594,595,595,596,596,597,597,598,598,599,599,600,600,601,601,601,602,602,602,603,603,603,604,604,604];
const SURAH_AYAT = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6];

function juzOfPage(p) { let j = 1; for (let i = 0; i < 30; i++) if (p >= JUZ_START[i]) j = i + 1; return j; }
function surahsOfPage(p) {
  /* السورة تظهر في الصفحة إن كانت بين صفحة بدايتها وصفحة بداية السورة التالية (تقريب: آخر صفحة قد تكون مشتركة) */
  const list = [];
  for (let s = 0; s < 114; s++) {
    const start = SURAH_START[s];
    const next = s < 113 ? SURAH_START[s + 1] : 605;
    if ((start <= p && p < next) || start === p) list.push(s + 1);
  }
  return list;
}
function pageLabel(p) {
  const ss = surahsOfPage(p);
  const names = ss.map(n => SURAH_NAMES[n - 1]);
  return `ص ${p} · ${names.join(' / ')}`;
}
function juzLabel(j) { return `الجزء ${j}`; }
function juzPages(j) { const a = JUZ_START[j - 1]; const b = j < 30 ? JUZ_START[j] - 1 : 604; const out = []; for (let p = a; p <= b; p++) out.push(p); return out; }

/* ===== أنواع الأخطاء ===== */
const ERROR_TYPES = [
  { id: 'hesitate', name: 'تردد', short: 'تردد' },
  { id: 'prompt', name: 'تلقين', short: 'تلقين' },
  { id: 'swap', name: 'إبدال كلمة', short: 'إبدال' },
  { id: 'jump', name: 'انتقال إلى موضع مشابه', short: 'مشابه' },
  { id: 'tajweed', name: 'تجويد', short: 'تجويد' },
  { id: 'skip', name: 'سقوط آية أو كلمة', short: 'سقوط' },
];

/* ===== الخطة اليومية المضمّنة =====
   الأيام: 6=السبت 0=الأحد 1=الاثنين 2=الثلاثاء 3=الأربعاء 4=الخميس 5=الجمعة (ترقيم JS)
   kind يحدد شاشة الجلسة وخطواتها. teacher: aya | asst
*/
const WORKDAYS = [6, 0, 1, 2, 3];
const THURSDAY = 4;

const SESSION_KINDS = {
  gate_new: { name: 'بوابة الأمس وحفظ الجديد', teacher: 'aya', steps: [
    { id: 'gate', text: 'بوابة الأمس: تسميع صفحة الأمس غيباً', min: 5, outcome: 'gate' },
    { id: 'memorize', text: 'حفظ الصفحة الجديدة بالتسلسل (ثلاثة مقاطع، آية آية، ثم الربط)', min: 25, timer: true },
    { id: 'first', text: 'التسميع الأول: الصفحة كاملة غيباً مرتين + سؤالا معنى', min: 10, outcome: 'first' },
  ]},
  near_review: { name: 'أوائل الآيات والمراجعة القريبة', teacher: 'asst', steps: [
    { id: 'awael', text: 'أوائل الآيات: يكتب أول كلمتين من كل آية في صفحة الأمس من الذاكرة، وتُصحَّح', min: 4, outcome: 'awael' },
    { id: 'near', text: 'المراجعة القريبة: صفحات الجزء الحالي غيباً، الأحدث أولاً', min: 20, outcome: 'near' },
    { id: 'tilawa', text: 'ورد النظر: 2–3 صفحات من الجزء القادم نظراً بالتجويد', min: 8 },
    { id: 'listen', text: 'سماع صفحة اليوم من القارئ مع المتابعة بالإصبع، 3 مرات', min: 8 },
  ]},
  karim_new: { name: 'بوابة الأمس وتلقين الجديد', teacher: 'aya', steps: [
    { id: 'gate', text: 'بوابة الأمس: تسميع مقطع الأمس غيباً', min: 3, outcome: 'gate' },
    { id: 'memorize', text: 'يقرأ المقطع الجديد نظراً، ثم تلقين آية آية بالتسلسل حتى يقوله غيباً', min: 14, timer: true },
    { id: 'first', text: 'التسميع الأول + سؤال من بطاقة السورة', min: 3, outcome: 'first' },
  ]},
  noon: { name: 'قرآن الظهر', teacher: 'asst', steps: [
    { id: 'second', text: 'التسميع الثاني لصفحة اليوم غيباً', min: 3, outcome: 'second' },
    { id: 'far', text: 'حصة البعيد من خريطة المصحف بالترتيب الدوري', min: 9, outcome: 'far' },
    { id: 'cards', text: '4 أسئلة من بطاقات الصفحات التي سُمّعت، بالتناوب', min: 3, outcome: 'cards' },
  ]},
  fluency: { name: 'الطلاقة القرائية', teacher: 'asst', steps: [
    { id: 'read', text: 'قراءة نظراً مصحَّحة: الصفحة الحالية تُكرر حتى تنزل تحت 3 دقائق', min: 20, outcome: 'fluency' },
    { id: 'tomorrow', text: 'قراءة مقطع الغد نظراً 3 مرات', min: 5 },
  ]},
  karim_asr: { name: 'التسميع الثاني ومراجعة السور', teacher: 'asst', steps: [
    { id: 'second', text: 'تسميع مقطع اليوم مع سورته من أولها', min: 3, outcome: 'second' },
    { id: 'far', text: 'مراجعة السور المحفوظة: 3–4 صفحات بالترتيب الدوري', min: 15, outcome: 'far' },
    { id: 'cards', text: 'سؤال من بطاقة كل سورة روجعت + لعبة معنى قصيرة', min: 7, outcome: 'cards' },
  ]},
  circle: { name: 'مجلس المعنى والتلقين لصفحة الغد', teacher: 'aya', steps: [
    { id: 'context', text: 'سياق صفحة الغد وقصتها وربطها بما قبلها', min: 8 },
    { id: 'words', text: 'معاني غريب الصفحة كله', min: 5 },
    { id: 'tadabbur', text: 'سؤال تدبر واحد، كل طفل يجيب بجملة', min: 5 },
    { id: 'talqeen', text: 'تلقين: تقرأين الآية ويرددان نظراً، جولتان', min: 7 },
    { id: 'card', text: 'كتابة بطاقة صفحة الغد (الأسئلة الأربعة)', min: 0, card: true },
  ]},
  third: { name: 'التسميع الثالث وآيات الصفراء', teacher: 'aya', steps: [
    { id: 'third', text: 'صفحة اليوم غيباً مرة', min: 3, outcome: 'third' },
    { id: 'yellow', text: 'آيات القائمة الصفراء لهذا اليوم', min: 2, outcome: 'yellow' },
  ]},
  karim_evening: { name: 'قصة الغد وتلقينه ثم التسميع الثالث', teacher: 'aya', steps: [
    { id: 'story', text: 'قصة مقطع الغد بجملة، كلمتاه الغريبتان، تلقينه 3 مرات، سماعه من القارئ', min: 10, card: true },
    { id: 'third', text: 'التسميع الثالث لمقطع اليوم', min: 5, outcome: 'third' },
  ]},
  prep: { name: 'بطاقات الغد وتلوين السجلات', teacher: 'aya', steps: [
    { id: 'color', text: 'تلوين صفحات اليوم من سجل المساعدة ومن تسميعاتك', min: 10, color: true },
    { id: 'cards', text: 'التأكد من بطاقات الغد للثلاثة', min: 10 },
  ]},
  /* الخميس */
  thu_recite: { name: 'سرد الأسبوع وفحص البعيد', teacher: 'aya', steps: [
    { id: 'week', text: 'سرد صفحات الأسبوع الخمس متصلة غيباً', min: 15, outcome: 'week' },
    { id: 'exam', text: 'فحص 5 صفحات بالقرعة من البعيد', min: 10, outcome: 'exam', lottery: true },
  ]},
  thu_yellow: { name: 'كتابة الصفراء والمتشابهات وتصفيتها', teacher: 'asst', steps: [
    { id: 'write', text: 'كتابة آيات القائمة الصفراء والمتشابهات كاملة مرة واحدة مع موضعها المشابه', min: 10 },
    { id: 'clear', text: 'تسميع كل آية منها مع التي قبلها والتي بعدها', min: 15, outcome: 'yellow' },
  ]},
  thu_karim: { name: 'سرد مقاطع الأسبوع وسورتان بالقرعة', teacher: 'aya', steps: [
    { id: 'week', text: 'سرد مقاطع الأسبوع متصلة', min: 10, outcome: 'week' },
    { id: 'exam', text: 'سورتان بالقرعة من المحفوظ', min: 10, outcome: 'exam', lottery: true },
  ]},
  thu_listen: { name: 'سماع صفحات الأسبوع القادم', teacher: 'asst', steps: [
    { id: 'listen', text: 'الصفحات الخمس التالية من القارئ مع المتابعة نظراً، مرتين', min: 20 },
  ]},
  thu_mutashabih: { name: 'مجلس المتشابهات', teacher: 'aya', steps: [
    { id: 'm', text: 'كل زوج سُجّل هذا الأسبوع: الموضعان جنباً إلى جنب، الفرق وسببه، ثم تسميعهما متتاليين', min: 20, mutashabih: true },
  ]},
  thu_quiz: { name: 'مسابقة بطاقات السور', teacher: 'asst', steps: [
    { id: 'q', text: 'أسئلة بطاقات سور الأسبوع وقصصها في لعبة', min: 20 },
  ]},
  thu_tadabbur: { name: 'حلقة التدبر', teacher: 'aya', steps: [
    { id: 't', text: 'كل طفل يعرض ما تتحدث عنه صفحات أسبوعه وقاعدة عملية طبّقها. «من أين في الآية أخذت هذا؟»', min: 20 },
  ]},
};

/* الجدول: start/end بصيغة HH:MM */
const PLAN = [];
function addSess(days, start, end, kind, child, teacher) {
  for (const d of days) PLAN.push({ day: d, start, end, kind, child, teacher: teacher || SESSION_KINDS[kind].teacher });
}
/* السبت–الأربعاء */
addSess(WORKDAYS, '07:00', '07:40', 'gate_new', 'dalal');
addSess(WORKDAYS, '07:00', '07:40', 'near_review', 'farah');
addSess(WORKDAYS, '07:50', '08:30', 'gate_new', 'farah');
addSess(WORKDAYS, '07:50', '08:30', 'near_review', 'dalal');
addSess(WORKDAYS, '08:30', '08:50', 'karim_new', 'karim');
addSess(WORKDAYS, '12:10', '12:35', 'fluency', 'karim');
addSess(WORKDAYS, '12:50', '13:05', 'noon', 'dalal');
addSess(WORKDAYS, '13:05', '13:20', 'noon', 'farah');
addSess(WORKDAYS, '15:20', '15:45', 'karim_asr', 'karim');
addSess(WORKDAYS, '18:00', '18:25', 'circle', 'both');
addSess(WORKDAYS, '18:25', '18:30', 'third', 'dalal');
addSess(WORKDAYS, '18:30', '18:35', 'third', 'farah');
addSess(WORKDAYS, '18:35', '18:50', 'karim_evening', 'karim');
addSess(WORKDAYS, '18:50', '19:10', 'prep', 'all');
/* الخميس */
addSess([THURSDAY], '07:00', '07:25', 'thu_recite', 'dalal');
addSess([THURSDAY], '07:00', '07:25', 'thu_yellow', 'farah');
addSess([THURSDAY], '07:35', '08:00', 'thu_recite', 'farah');
addSess([THURSDAY], '07:35', '08:00', 'thu_yellow', 'dalal');
addSess([THURSDAY], '08:10', '08:30', 'thu_karim', 'karim');
addSess([THURSDAY], '08:10', '08:30', 'thu_listen', 'both');
addSess([THURSDAY], '08:40', '09:00', 'thu_mutashabih', 'both');
addSess([THURSDAY], '08:40', '09:00', 'thu_quiz', 'karim');
addSess([THURSDAY], '09:00', '09:20', 'thu_tadabbur', 'both');

const DAY_NAMES = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
