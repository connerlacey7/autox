CREATE TABLE seasons (
  id    INT AUTO_INCREMENT PRIMARY KEY,
  year  INT NOT NULL UNIQUE
);

CREATE TABLE events (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  season_id  INT NOT NULL,
  event_num  INT NOT NULL,
  event_date DATE,
  site       VARCHAR(100),
  UNIQUE (season_id, event_num),
  FOREIGN KEY (season_id) REFERENCES seasons(id)
);

CREATE TABLE drivers (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  first_name     VARCHAR(50) NOT NULL,
  last_name      VARCHAR(50) NOT NULL,
  member_number  VARCHAR(20) NULL UNIQUE,
  region         VARCHAR(50) NULL
);

CREATE TABLE vehicles (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  driver_id  INT NOT NULL,
  year       INT,
  make       VARCHAR(50),
  model      VARCHAR(50),
  color      VARCHAR(30),
  nickname   VARCHAR(50),
  FOREIGN KEY (driver_id) REFERENCES drivers(id)
);

CREATE TABLE results (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  event_id     INT NOT NULL,
  driver_id    INT NOT NULL,
  vehicle_id   INT,
  class        VARCHAR(20) NOT NULL,
  car_number   INT,
  raw_time     DECIMAL(8,3) NOT NULL,
  pax_index    DECIMAL(5,3) NOT NULL,
  pax_time     DECIMAL(8,3) NOT NULL,
  cones        INT NOT NULL DEFAULT 0,
  overall_pos  INT,
  class_pos    INT,
  UNIQUE (event_id, driver_id, class),
  FOREIGN KEY (event_id)   REFERENCES events(id),
  FOREIGN KEY (driver_id)  REFERENCES drivers(id),
  FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);

CREATE TABLE pax_indices (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  season_id INT,
  class     VARCHAR(20) NOT NULL,
  idx       DECIMAL(5,3) NOT NULL,
  UNIQUE (season_id, class),
  FOREIGN KEY (season_id) REFERENCES seasons(id)
);

CREATE TABLE runs (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  result_id  INT NOT NULL,
  run_num    INT NOT NULL,
  raw_time   DECIMAL(8,3),
  cones      INT NOT NULL DEFAULT 0,
  dnf        TINYINT(1) NOT NULL DEFAULT 0,
  rerun      TINYINT(1) NOT NULL DEFAULT 0,
  UNIQUE (result_id, run_num),
  FOREIGN KEY (result_id) REFERENCES results(id)
);
