-- setup.sql
-- Create a sample IMDB reviews table and load a few rows for testing the
-- jev_sentiment UDSF.
--
-- Run as:  vsql -f setup.sql   (or paste into your SQL client)

-- Drop any existing copy so the script is idempotent.
DROP TABLE IF EXISTS imdb_sample;

CREATE TABLE imdb_sample (
    filename  varchar(256),
    sentiment varchar(10),
    review    varchar(32767)
);

INSERT INTO imdb_sample (filename, sentiment, review) VALUES
('sample_001.txt', '1', 'I absolutely loved this movie! The acting was superb and the story kept me on the edge of my seat from start to finish. A fantastic experience I would recommend to everyone.'),
('sample_002.txt', '1', 'A heartwarming and beautifully shot film. The performances were top-notch and I left the theater feeling genuinely happy. One of the best movies I have seen this year.'),
('sample_003.txt', '0', 'This was a complete waste of time. The plot made no sense and the acting was wooden. I could barely sit through the whole thing and would not recommend it to anyone.'),
('sample_004.txt', '0', 'Terrible. The characters were unlikeable, the dialogue was cringeworthy, and the pacing dragged on forever. I regret spending money on a ticket for this mess.'),
('sample_005.txt', '1', 'A delightful surprise. Clever writing, charming characters, and a satisfying ending. I went in with low expectations and came out thoroughly entertained.');

COMMIT;
