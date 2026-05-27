const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, LevelFormat, AlignmentType, BorderStyle, WidthType,
  ShadingType, PageBreak,
} = require("docx");

// Цвета
const BRAND = "22C55E";
const HEADER_BG = "F0FDF4";
const ROW_ALT = "FAFAFA";
const BORDER_COLOR = "D1D5DB";
const TEXT_HINT = "6B7280";

const border = { style: BorderStyle.SINGLE, size: 6, color: BORDER_COLOR };
const borders = { top: border, bottom: border, left: border, right: border };

function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, ...opts })],
    spacing: { after: 120 },
  });
}

function h(text, level) {
  return new Paragraph({
    heading: level,
    children: [new TextRun({ text, bold: true })],
    spacing: { before: 280, after: 160 },
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    children: [new TextRun({ text })],
    spacing: { after: 80 },
  });
}

function num(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "numbers", level },
    children: [new TextRun({ text })],
    spacing: { after: 80 },
  });
}

function richP(parts, opts = {}) {
  return new Paragraph({
    children: parts.map((part) => new TextRun(part)),
    spacing: { after: 120 },
    ...opts,
  });
}

function cell(text, opts = {}) {
  const isHeader = opts.header === true;
  const widthDxa = opts.widthDxa || 4680;
  return new TableCell({
    borders,
    width: { size: widthDxa, type: WidthType.DXA },
    shading: isHeader
      ? { fill: HEADER_BG, type: ShadingType.CLEAR }
      : (opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined),
    margins: { top: 100, bottom: 100, left: 140, right: 140 },
    children: [
      new Paragraph({
        children: [new TextRun({ text, bold: !!isHeader })],
      }),
    ],
  });
}

function table(rows, columnWidths) {
  return new Table({
    width: { size: columnWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths,
    rows: rows.map(
      (row) =>
        new TableRow({
          children: row.map((c, i) =>
            cell(c.text, { ...c, widthDxa: columnWidths[i] })
          ),
        })
    ),
  });
}

function divider() {
  return new Paragraph({
    children: [new TextRun("")],
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 6, color: BRAND, space: 1 },
    },
    spacing: { before: 60, after: 200 },
  });
}

const doc = new Document({
  creator: "Sales Doctor",
  title: "Инструкция: ЗВС-бот",
  description: "Инструкция для сотрудников по работе с ЗВС-ботом @finzvsbot",
  styles: {
    default: {
      document: { run: { font: "Arial", size: 22 } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "111827" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: BRAND },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "111827" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "numbers",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        // Заголовок документа
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({
              text: "SALES DOCTOR",
              bold: true,
              size: 24,
              color: BRAND,
            }),
          ],
          spacing: { after: 100 },
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Инструкция для сотрудников", bold: true, size: 44 }),
          ],
          spacing: { after: 80 },
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({
              text: "ЗВС-бот @finzvsbot — заявки на выдачу средств",
              italics: true,
              color: TEXT_HINT,
              size: 22,
            }),
          ],
          spacing: { after: 240 },
        }),
        divider(),

        // ─── Как начать пользоваться ───
        h("Как начать пользоваться", HeadingLevel.HEADING_2),
        num("Открой бота @finzvsbot в Telegram"),
        num("Нажми «Start» или напиши /start"),
        num("Бот скажет «нет доступа» и пришлёт директору запрос"),
        num("Жди — директор одобряет в течение дня, бот сразу пришлёт «Доступ открыт»"),
        num("Нажми /start ещё раз — увидишь две кнопки: «Подать заявку» и «Мои заявки»"),

        // ─── Когда подавать заявки ───
        h("Когда подавать заявки", HeadingLevel.HEADING_2),
        p("Цикл выплат — недельный (Вт → Пн → Вт):"),
        table(
          [
            [
              { text: "День", header: true },
              { text: "Что происходит", header: true },
            ],
            [
              { text: "Вторник" },
              { text: "Бухгалтер выдаёт деньги по одобренным заявкам прошлой недели. Открыто окно подачи новых заявок." },
            ],
            [
              { text: "Среда — Воскресенье", fill: ROW_ALT },
              { text: "Подаёшь заявки на любые рабочие нужды.", fill: ROW_ALT },
            ],
            [
              { text: "Понедельник" },
              { text: "Последний день подачи. Директор разбирает и одобряет/отклоняет." },
            ],
            [
              { text: "Вторник", fill: ROW_ALT },
              { text: "Деньги получаешь.", fill: ROW_ALT },
            ],
          ],
          [2500, 6860]
        ),
        new Paragraph({ children: [new TextRun("")], spacing: { after: 160 } }),
        richP([
          { text: "Дедлайн: ", bold: true },
          { text: "подать заявку до 23:59 понедельника. Если опоздал — попадёт в следующий вторник, неделя ожидания." },
        ]),
        richP([
          { text: "Срочно надо до вторника? ", bold: true },
          { text: "Позвони директору лично. Заявка через бот всё равно нужна для учёта." },
        ]),

        // ─── Как подать заявку ───
        h("Как подать заявку", HeadingLevel.HEADING_2),
        num("Жми «Подать заявку» в чате с ботом"),
        num("Откроется форма прямо в Telegram — три поля:"),
        bullet("Сумма (в тенге, только число)", 0),
        bullet("На что (коротко — на что деньги)", 0),
        bullet("С какого счёта (Халык / Каспи / Наличка)", 0),
        num("Жми «Отправить директору»"),
        num("У тебя в чате появится «Заявка №X — ожидает»"),
        num("Когда директор одобрит/отклонит — это же сообщение обновится на «одобрено», «отклонено» или «на доработку»"),

        // ─── Что писать в «На что» ───
        h("Что писать в «На что»", HeadingLevel.HEADING_2),
        new Paragraph({
          children: [new TextRun({ text: "Правильно — конкретно:", bold: true })],
          spacing: { after: 100 },
        }),
        bullet("Ремонт принтера в офисе"),
        bullet("Канцелярия — бумага, ручки на месяц"),
        bullet("Реклама Facebook за май"),
        bullet("Заказ воды в офис"),
        bullet("Подписка Slack на 3 месяца"),
        bullet("Печать визиток для команды"),
        new Paragraph({
          children: [new TextRun({ text: "Неправильно — расплывчато:", bold: true })],
          spacing: { before: 160, after: 100 },
        }),
        bullet("Расходы"),
        bullet("На работу"),
        bullet("Срочно надо"),
        bullet("По договорённости"),
        p("Если описание короткое и непонятное — директор отправит «На доработку», переписать придётся."),

        // ─── С какого счёта ───
        h("С какого счёта правильно выбирать", HeadingLevel.HEADING_2),
        table(
          [
            [
              { text: "Счёт", header: true },
              { text: "Когда выбирать", header: true },
            ],
            [
              { text: "Халык" },
              { text: "Для безналичных переводов на казахстанские счета" },
            ],
            [
              { text: "Каспи", fill: ROW_ALT },
              { text: "Для оплат через Kaspi — быстрее, удобнее для мелочей", fill: ROW_ALT },
            ],
            [
              { text: "Наличка" },
              { text: "Когда нужен кеш на руки" },
            ],
          ],
          [2000, 7360]
        ),
        new Paragraph({ children: [new TextRun("")], spacing: { after: 160 } }),
        p("Если не уверен — выбирай Каспи или спроси у бухгалтера."),

        // ─── Что нельзя ───
        h("Что нельзя", HeadingLevel.HEADING_2),
        bullet("Завышать сумму «с запасом» — пиши точную. Перерасход подаётся отдельной заявкой"),
        bullet("Дублировать одну и ту же заявку — если забыл что подавал, проверь «Мои заявки»"),
        bullet("Просить деньги у бухгалтера в обход бота — учёт ломается"),
        bullet("Оставлять пустое описание — будет «На доработку»"),

        // ─── Как узнать статус ───
        h("Как узнать статус заявки", HeadingLevel.HEADING_2),
        p("Кнопка «Мои заявки» покажет 10 последних твоих заявок со статусом."),
        p("Плюс то самое сообщение, которое бот прислал при подаче, автоматически обновляется — ты сразу видишь решение."),

        // ─── Если отклонили / доработка ───
        h("Если отклонили или на доработку", HeadingLevel.HEADING_2),
        p("Директор напишет причину прямо в сообщении. Пример:"),
        new Paragraph({
          spacing: { before: 60, after: 120 },
          children: [
            new TextRun({
              text: "Заявка №35 — отклонено\n80 000 тг · Халык\nДорогая техника\n\nСначала обсудим, что именно покупаешь",
              font: "Courier New",
              size: 20,
            }),
          ],
        }),
        p("Прочитай причину, поговори с директором, при необходимости подай новую заявку с учётом замечаний."),

        // ─── Команды ───
        h("Команды бота", HeadingLevel.HEADING_2),
        table(
          [
            [
              { text: "Команда", header: true },
              { text: "Что делает", header: true },
            ],
            [{ text: "/start" }, { text: "Главное меню" }],
            [{ text: "/zayavka", fill: ROW_ALT }, { text: "Подать заявку (то же что кнопка)", fill: ROW_ALT }],
            [{ text: "/history" }, { text: "Мои заявки (то же что кнопка)" }],
            [{ text: "/cancel", fill: ROW_ALT }, { text: "Отменить ввод заявки если ошибся", fill: ROW_ALT }],
          ],
          [2500, 6860]
        ),
        new Paragraph({ children: [new TextRun("")], spacing: { after: 160 } }),

        // ─── Если бот не отвечает ───
        h("Если бот не отвечает", HeadingLevel.HEADING_2),
        bullet("Проверь интернет"),
        bullet("Закрой Telegram и открой заново"),
        bullet("Если форма не открывается — нажми /start чтобы получить свежую кнопку"),
        bullet("Если совсем не работает — пиши директору лично"),

        // Главное правило
        new Paragraph({ children: [new TextRun("")], spacing: { before: 240 } }),
        divider(),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 80, after: 80 },
          children: [
            new TextRun({ text: "Главное правило", bold: true, size: 26 }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 80 },
          children: [
            new TextRun({
              text: "Одна заявка = одна реальная нужда с понятным описанием.",
              size: 22,
            }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 240 },
          children: [
            new TextRun({
              text: "Чем понятнее напишешь — тем быстрее одобрят.",
              size: 22,
              color: TEXT_HINT,
            }),
          ],
        }),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  const outPath = path.resolve(process.argv[2] || "Инструкция_ЗВС_бот.docx");
  fs.writeFileSync(outPath, buf);
  console.log("OK:", outPath);
});
