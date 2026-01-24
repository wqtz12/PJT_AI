CREATE TABLE experiences (
   id INT PRIMARY KEY,
   content TEXT,
   type ENUM('work', 'project'),
   start_date DATE,
   end_date DATE,
   keywords VARCHAR(255),
   metadata JSON
);
