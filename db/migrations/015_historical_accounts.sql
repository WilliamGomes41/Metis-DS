-- Additive: no existing account is retired by this migration.
ALTER TABLE workflow.accounts ADD COLUMN IF NOT EXISTS retirement JSONB;

CREATE OR REPLACE FUNCTION workflow.guard_account_retirement() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.retirement IS NOT NULL
       AND NEW.retirement IS DISTINCT FROM OLD.retirement THEN
        RAISE EXCEPTION 'account_retirement_is_terminal';
    END IF;
    IF NEW.retirement IS NOT NULL THEN
        IF jsonb_typeof(NEW.retirement) <> 'object'
           OR COALESCE(NEW.retirement->>'actor', '') = ''
           OR COALESCE(NEW.retirement->>'reason', '') = ''
           OR COALESCE(NEW.retirement->>'at', '') = '' THEN
            RAISE EXCEPTION 'account_retirement_evidence_required';
        END IF;
        NEW.password_salt := '';
        NEW.password_hash := '';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_account_retirement ON workflow.accounts;
CREATE TRIGGER trg_account_retirement BEFORE INSERT OR UPDATE ON workflow.accounts
FOR EACH ROW EXECUTE FUNCTION workflow.guard_account_retirement();

CREATE OR REPLACE FUNCTION workflow.revoke_retired_account_sessions() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.retirement IS NOT NULL THEN
        UPDATE workflow.sessions SET revoked_at = CURRENT_TIMESTAMP
        WHERE account_id = NEW.account_id AND revoked_at IS NULL;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_retired_account_sessions ON workflow.accounts;
CREATE TRIGGER trg_retired_account_sessions AFTER UPDATE ON workflow.accounts
FOR EACH ROW EXECUTE FUNCTION workflow.revoke_retired_account_sessions();

CREATE OR REPLACE FUNCTION workflow.guard_retired_account_session() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE retired JSONB;
BEGIN
    -- Revoked historical sessions may be restored, but never revived.
    IF NEW.revoked_at IS NULL THEN
        SELECT retirement INTO retired FROM workflow.accounts
        WHERE account_id = NEW.account_id FOR SHARE;
        IF retired IS NOT NULL THEN
            RAISE EXCEPTION 'account_retired';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_guard_retired_account_session ON workflow.sessions;
CREATE TRIGGER trg_guard_retired_account_session BEFORE INSERT OR UPDATE ON workflow.sessions
FOR EACH ROW EXECUTE FUNCTION workflow.guard_retired_account_session();
