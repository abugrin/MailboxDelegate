# Скрипт для настройки делегирования почтовых ящиков Яндекс 360 для бизнеса

### Используются методы API Яндекс 360:

https://yandex.ru/dev/api360/doc/ref/DelegatedMailboxService.html

### Настройка клиентских приложений:

https://yandex.ru/support/mail-business/mail-clients/shared-mailboxes.html

### Использование

1) Для запуска настройки необходио создать токен приложения с соответствующими правами (см. выше описание API):

    ```ya360_admin:mail_write_shared_mailbox_inventory``` — управление правами доступа к почтовым ящикам

    ```ya360_admin:mail_read_shared_mailbox_inventory``` — чтение информации о правах доступа к почтовым ящикам

2) Подготовить .csv файл для импорта со следующей структурой (см. пример in.csv)

    - 1 строка: ResourceMail, ActorMail, ImapFullAccess, SendAs, SendOnBehalf
    - 2 строка: resource_user1@domain, actor_user@domain, true, true, true // Последние 3 параметра либо `true` либо `false` 

   итд

3) В файле config.py указать 
   - TOKEN=токен полученый на шаге 1)
   - ORG_ID=ID Организации Яндекс 360

4) Запуск:
   - Установить [Python](https://www.python.org/)
   - Перейти в папку с проектом и создать виртуальное окружение: `python -m venv .venv`
   - Запустить скрипт активации виртуального окружения: На Windows `.venv\Scripts\activate.bat`
   - Установить Poetry: `pip install poetry`
   - Установить зависимости: `poetry install`
   - Запустить скрипт. Параметры запуска:
           `python delegate.py -f имя_файла.csv` - запускает процесс настройки делегирования из файла .csv
           `python delegate.py -q` - запрашивает текущую конфигурацию делегирования и сохраняет в файл current_records.csv