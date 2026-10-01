-- SPDX-License-Identifier: Apache-2.0
-- cdrs.unbacked_claims: what the bot told the caller it was doing, or had done,
-- in a turn with no tool call behind it (#44).
--
-- The flow sees only tool results and silence, so a bot that says "I'm
-- transferring you" and never calls transfer_to_agent leaves a row that reads
-- as an ordinary conversation, contained if it later hung up properly. The
-- column records each kind of claim once, so those calls can be found and
-- kept out of containment figures without anyone reading transcripts.
--
-- A new column with an empty default narrows nothing, so rows already written
-- satisfy the CHECK as they stand. Down drops the column and with it the
-- record of which calls made such claims; the transcripts still hold the words.

-- +goose Up
ALTER TABLE cdrs ADD COLUMN unbacked_claims text[] NOT NULL DEFAULT '{}'
    CONSTRAINT cdrs_unbacked_claims_check
    CHECK (unbacked_claims <@ ARRAY['TRANSFER', 'LOOKUP', 'MESSAGE', 'FAREWELL']::text[]);

-- +goose Down
ALTER TABLE cdrs DROP COLUMN unbacked_claims;
