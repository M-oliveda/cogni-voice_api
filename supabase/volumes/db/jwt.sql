-- SPDX-License-Identifier: GPL-2.0-or-later
--
-- Local only: JWT expiry setting read by Supabase functions.
-- Adapted from Supabase's self-hosting setup (docker/volumes/db/jwt.sql).
\set jwt_exp `echo "$JWT_EXP"`

ALTER DATABASE postgres SET "app.settings.jwt_exp" TO :'jwt_exp';
