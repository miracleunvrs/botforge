from .schemas import FlowDefinition, TemplateInfo

TEMPLATES: list[TemplateInfo] = [
    TemplateInfo(
        id="faq",
        title="FAQ бот",
        description="Ответы на частые вопросы: доставка, оплата, возврат",
        definition=FlowDefinition.model_validate(
            {
                "start_id": "welcome",
                "nodes": [
                    {"id": "welcome", "type": "message", "title": "Приветствие", "text": "Привет! Я помогу с вопросами. Выберите тему:", "next_id": "menu"},
                    {"id": "menu", "type": "choice", "title": "Меню FAQ", "text": "Что вас интересует?", "choices": [
                        {"label": "Доставка", "next_id": "delivery"},
                        {"label": "Оплата", "next_id": "payment"},
                        {"label": "Возврат", "next_id": "refund"},
                    ]},
                    {"id": "delivery", "type": "message", "title": "Доставка", "text": "Доставляем за 1-3 дня по всей России. Стоимость от 300₽.", "next_id": "again"},
                    {"id": "payment", "type": "message", "title": "Оплата", "text": "Принимаем карты, СБП и наличные при получении.", "next_id": "again"},
                    {"id": "refund", "type": "message", "title": "Возврат", "text": "Возврат в течение 14 дней, если товар не использовался.", "next_id": "again"},
                    {"id": "again", "type": "choice", "title": "Еще вопрос?", "text": "Могу помочь с чем-то еще?", "choices": [
                        {"label": "Да", "next_id": "menu"},
                        {"label": "Нет", "next_id": "bye"},
                    ]},
                    {"id": "bye", "type": "end", "title": "Завершение", "text": "Спасибо за обращение!"},
                ],
            }
        ),
    ),
    TemplateInfo(
        id="lead",
        title="Сбор заявок",
        description="Собирает имя и телефон, ветвит по условию",
        definition=FlowDefinition.model_validate(
            {
                "start_id": "welcome",
                "nodes": [
                    {"id": "welcome", "type": "message", "title": "Приветствие", "text": "Здравствуйте! Оставьте заявку и мы перезвоним.", "next_id": "ask_name"},
                    {"id": "ask_name", "type": "input", "title": "Имя", "text": "Как к вам обращаться?", "next_id": "ask_phone"},
                    {"id": "ask_phone", "type": "input", "title": "Телефон", "text": "Укажите номер телефона:", "next_id": "check_phone"},
                    {"id": "check_phone", "type": "condition", "title": "Проверка телефона", "text": "Проверяем номер…", "condition_value": "+", "true_next_id": "success", "false_next_id": "retry"},
                    {"id": "retry", "type": "message", "title": "Уточнение", "text": "Похоже, номер указан без кода страны. Наш менеджер всё равно свяжется с вами!", "next_id": "success"},
                    {"id": "success", "type": "end", "title": "Готово", "text": "Спасибо! Заявка принята. Мы позвоним в течение 15 минут."},
                ],
            }
        ),
    ),
    TemplateInfo(
        id="booking",
        title="Запись на услугу",
        description="Выбор слота, имя и подтверждение",
        definition=FlowDefinition.model_validate(
            {
                "start_id": "welcome",
                "nodes": [
                    {"id": "welcome", "type": "message", "title": "Приветствие", "text": "Добро пожаловать! Выберите удобное время для записи:", "next_id": "slots"},
                    {"id": "slots", "type": "choice", "title": "Слоты", "text": "Свободные окна на сегодня:", "choices": [
                        {"label": "10:00", "next_id": "ask_name"},
                        {"label": "14:00", "next_id": "ask_name"},
                        {"label": "18:00", "next_id": "ask_name"},
                    ]},
                    {"id": "ask_name", "type": "input", "title": "Имя", "text": "На какое имя записать?", "next_id": "confirm"},
                    {"id": "confirm", "type": "end", "title": "Подтверждение", "text": "Отлично! Вы записаны. Ждём вас в выбранное время."},
                ],
            }
        ),
    ),
    TemplateInfo(
        id="feedback",
        title="Обратная связь",
        description="Собирает отзыв и ветвит реакцию по условию",
        definition=FlowDefinition.model_validate(
            {
                "start_id": "welcome",
                "nodes": [
                    {"id": "welcome", "type": "message", "title": "Приветствие", "text": "Нам важно ваше мнение! Оставьте отзыв:", "next_id": "ask_text"},
                    {"id": "ask_text", "type": "input", "title": "Отзыв", "text": "Напишите, что понравилось или что улучшить:", "next_id": "check_sentiment"},
                    {"id": "check_sentiment", "type": "condition", "title": "Тональность", "text": "Анализируем…", "condition_value": "спасибо", "true_next_id": "thanks_pos", "false_next_id": "thanks_any"},
                    {"id": "thanks_pos", "type": "end", "title": "Позитив", "text": "Спасибо за тёплые слова! Будем стараться и дальше 😊"},
                    {"id": "thanks_any", "type": "end", "title": "Благодарность", "text": "Спасибо за обратную связь! Мы учтём ваши пожелания."},
                ],
            }
        ),
    ),
]
