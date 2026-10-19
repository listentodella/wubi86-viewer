/** Copy-typing passages (classical Chinese, public domain) and the comparison logic behind the drill. */

export interface Passage {
  id: string
  title: string
  author: string
  text: string
}

export const PASSAGES: Passage[] = [
  {
    id: 'loushi',
    title: '陋室铭',
    author: '刘禹锡',
    text: `山不在高，有仙则名。水不在深，有龙则灵。斯是陋室，惟吾德馨。苔痕上阶绿，草色入帘青。谈笑有鸿儒，往来无白丁。可以调素琴，阅金经。无丝竹之乱耳，无案牍之劳形。南阳诸葛庐，西蜀子云亭。孔子云：何陋之有？`,
  },
  {
    id: 'ailian',
    title: '爱莲说',
    author: '周敦颐',
    text: `水陆草木之花，可爱者甚蕃。晋陶渊明独爱菊。自李唐来，世人甚爱牡丹。予独爱莲之出淤泥而不染，濯清涟而不妖，中通外直，不蔓不枝，香远益清，亭亭净植，可远观而不可亵玩焉。
予谓菊，花之隐逸者也；牡丹，花之富贵者也；莲，花之君子者也。噫！菊之爱，陶后鲜有闻。莲之爱，同予者何人？牡丹之爱，宜乎众矣。`,
  },
  {
    id: 'yueyang',
    title: '岳阳楼记',
    author: '范仲淹',
    text: `予观夫巴陵胜状，在洞庭一湖。衔远山，吞长江，浩浩汤汤，横无际涯；朝晖夕阴，气象万千。此则岳阳楼之大观也，前人之述备矣。然则北通巫峡，南极潇湘，迁客骚人，多会于此，览物之情，得无异乎？
嗟夫！予尝求古仁人之心，或异二者之为，何哉？不以物喜，不以己悲；居庙堂之高则忧其民，处江湖之远则忧其君。是进亦忧，退亦忧。然则何时而乐耶？其必曰先天下之忧而忧，后天下之乐而乐乎。噫！微斯人，吾谁与归？`,
  },
  {
    id: 'tengwang',
    title: '滕王阁序',
    author: '王勃',
    text: `时维九月，序属三秋。潦水尽而寒潭清，烟光凝而暮山紫。俨骖騑于上路，访风景于崇阿。临帝子之长洲，得天人之旧馆。层峦耸翠，上出重霄；飞阁流丹，下临无地。鹤汀凫渚，穷岛屿之萦回；桂殿兰宫，即冈峦之体势。
披绣闼，俯雕甍，山原旷其盈视，川泽纡其骇瞩。闾阎扑地，钟鸣鼎食之家；舸舰弥津，青雀黄龙之舳。云销雨霁，彩彻区明。落霞与孤鹜齐飞，秋水共长天一色。`,
  },
  {
    id: 'lanting',
    title: '兰亭集序',
    author: '王羲之',
    text: `永和九年，岁在癸丑，暮春之初，会于会稽山阴之兰亭，修禊事也。群贤毕至，少长咸集。此地有崇山峻岭，茂林修竹，又有清流激湍，映带左右，引以为流觞曲水，列坐其次。虽无丝竹管弦之盛，一觞一咏，亦足以畅叙幽情。
是日也，天朗气清，惠风和畅。仰观宇宙之大，俯察品类之盛，所以游目骋怀，足以极视听之娱，信可乐也。`,
  },
  {
    id: 'zuiweng',
    title: '醉翁亭记',
    author: '欧阳修',
    text: `环滁皆山也。其西南诸峰，林壑尤美，望之蔚然而深秀者，琅琊也。山行六七里，渐闻水声潺潺而泻出于两峰之间者，酿泉也。峰回路转，有亭翼然临于泉上者，醉翁亭也。作亭者谁？山之僧智仙也。名之者谁？太守自谓也。
太守与客来饮于此，饮少辄醉，而年又最高，故自号曰醉翁也。醉翁之意不在酒，在乎山水之间也。山水之乐，得之心而寓之酒也。`,
  },
  {
    id: 'chibi',
    title: '赤壁赋',
    author: '苏轼',
    text: `壬戌之秋，七月既望，苏子与客泛舟游于赤壁之下。清风徐来，水波不兴。举酒属客，诵明月之诗，歌窈窕之章。少焉，月出于东山之上，徘徊于斗牛之间。白露横江，水光接天。纵一苇之所如，凌万顷之茫然。
浩浩乎如冯虚御风，而不知其所止；飘飘乎如遗世独立，羽化而登仙。`,
  },
]

const HAN = /[\p{Script=Han}〇]/u
export const isHan = (ch: string) => HAN.test(ch)
/** Only Han characters are compared: punctuation, spaces and line breaks are skipped. */
export const hanOf = (s: string) => [...s].filter(isHan)

export type CharState = 'plain' | 'pending' | 'current' | 'correct' | 'wrong'

export interface Token {
  ch: string
  state: CharState
  /** index among the Han characters, -1 for punctuation */
  index: number
}

export interface PassageState {
  typed: string[]
  correct: number
  /** typed characters that do not match, including anything typed past the end */
  wrong: number
  /** typed characters beyond the end of the passage */
  extra: number
  /** consecutive correct characters ending at the last typed one */
  streak: number
  best: number
  score: number
  /** how many Han characters have been entered */
  cursor: number
  done: boolean
}

/**
 * All statistics are derived from the typed string, so deleting and retyping
 * cannot farm points: the score only reflects the current text.
 */
export function evaluatePassage(ref: string[], typed: string[]): PassageState {
  const n = Math.min(typed.length, ref.length)
  let correct = 0
  let score = 0
  let run = 0
  let best = 0
  for (let i = 0; i < n; i++) {
    if (typed[i] === ref[i]) {
      run++
      best = Math.max(best, run)
      correct++
      score += 10 + Math.min(run - 1, 10) * 2
    } else {
      run = 0
    }
  }
  return {
    typed,
    correct,
    wrong: typed.length - correct,
    extra: Math.max(0, typed.length - ref.length),
    streak: run,
    best,
    score,
    cursor: Math.min(typed.length, ref.length),
    done: ref.length > 0 && typed.length >= ref.length,
  }
}

export function passageTokens(text: string, typed: string[], done: boolean): Token[] {
  let index = 0
  return [...text].map((ch) => {
    if (!isHan(ch)) return { ch, state: 'plain', index: -1 }
    const i = index++
    const state: CharState =
      i < typed.length ? (typed[i] === ch ? 'correct' : 'wrong') : i === typed.length && !done ? 'current' : 'pending'
    return { ch, state, index: i }
  })
}

export const typingAccuracy = (s: PassageState) => (s.typed.length ? s.correct / s.typed.length : 1)

export const charsPerMinute = (count: number, ms: number) => (ms > 500 ? Math.round((count * 60_000) / ms) : 0)
