# Reston Analytics — Инструкция по деплою

## Сервер
- **IP:** 185.98.7.66
- **Домен:** https://reston.kz
- **ОС:** Ubuntu 22.04
- **Папка проекта:** /opt/reston

---

## Подключение к серверу

```bash
ssh root@185.98.7.66
```
Введи пароль от сервера.

---

## Обновить сайт (после изменений в коде)

### Шаг 1 — На MacBook: запушить изменения в GitHub
```bash
cd /Users/shalkar/Desktop/wastecontrol-web
git add -A
git commit -m "описание изменений"
git push origin main
```

### Шаг 2 — На сервере: скачать и перезапустить
```bash
ssh root@185.98.7.66
cd /opt/reston
git pull
docker-compose up -d --build
```

---

## Полезные команды на сервере

### Проверить статус контейнеров
```bash
cd /opt/reston && docker-compose ps
```

### Посмотреть логи бэкенда
```bash
cd /opt/reston && docker-compose logs backend --tail=50
```

### Перезапустить всё
```bash
cd /opt/reston && docker-compose restart
```

### Остановить сайт
```bash
cd /opt/reston && docker-compose down
```

### Запустить сайт
```bash
cd /opt/reston && docker-compose up -d
```

---

## База данных

### Подключиться к БД с MacBook (TablePlus / pgAdmin)
```
Host:     185.98.7.66
Port:      5432
Database:  wastecontrol
User:      wastecontrol_user
Password:  WC_dev_pass_2026
```

### Подключиться к БД прямо на сервере
```bash
sudo -u postgres psql -d wastecontrol
```

### Сделать резервную копию БД
```bash
pg_dump -U wastecontrol_user -h localhost -d wastecontrol -Fc -f /tmp/backup.dump
```

### Скачать резервную копию на MacBook
```bash
scp root@185.98.7.66:/tmp/backup.dump ~/Desktop/backup.dump
```

---

## SSL сертификат

Сертификат **бесплатный** от Let's Encrypt, продлевается **автоматически**.  
Истекает: **2026-07-16**

Если нужно продлить вручную:
```bash
certbot renew
```

---

## GitHub репозиторий

- **URL:** https://github.com/Shalkar-Mukazhan/reston-analytics
- **Ветка:** main

---

## Если сайт упал — что делать

1. Подключись к серверу: `ssh root@185.98.7.66`
2. Проверь контейнеры: `cd /opt/reston && docker-compose ps`
3. Посмотри логи: `docker-compose logs backend --tail=30`
4. Перезапусти: `docker-compose restart`
5. Если не помогло: `docker-compose down && docker-compose up -d`
