FROM postgres:17.2

RUN apt-get update && apt-get -y install postgresql-17-cron

COPY 01-schema.sql /docker-entrypoint-initdb.d/01-schema.sql
RUN chmod 644 /docker-entrypoint-initdb.d/01-schema.sql
