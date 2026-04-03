--
-- PostgreSQL database dump
--

\restrict hIJudC3OqVAvzzyuIUzf6KifGnBcSIlmVgpYiae8IBukGc1JoGeGpkMQnrwZEyA

-- Dumped from database version 18.0 (Postgres.app)
-- Dumped by pg_dump version 18.0 (Postgres.app)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: delivery_mode_enum; Type: TYPE; Schema: public; Owner: mac
--

CREATE TYPE public.delivery_mode_enum AS ENUM (
    'online',
    'on-site',
    'blended',
    'hybrid'
);


ALTER TYPE public.delivery_mode_enum OWNER TO mac;

--
-- Name: level_enum; Type: TYPE; Schema: public; Owner: mac
--

CREATE TYPE public.level_enum AS ENUM (
    'Bachelor',
    'Master',
    'PhD',
    'Postgraduate',
    'Professional',
    'Continuing Education'
);


ALTER TYPE public.level_enum OWNER TO mac;

--
-- Name: programme_type_enum; Type: TYPE; Schema: public; Owner: mac
--

CREATE TYPE public.programme_type_enum AS ENUM (
    'Bachelor',
    'Master',
    'PhD',
    'Graduate Certificate',
    'Micro-credential',
    'CAS',
    'DAS',
    'MAS',
    'Lifelong Learning',
    'Continuing Education',
    'Professional'
);


ALTER TYPE public.programme_type_enum OWNER TO mac;

--
-- Name: compute_offering_variant_sig(); Type: FUNCTION; Schema: public; Owner: mac
--

CREATE FUNCTION public.compute_offering_variant_sig() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.variant_sig := md5(
    coalesce(to_char(NEW.start_date,'YYYY-MM-DD'),'') || '|' ||
    coalesce(to_char(NEW.end_date,'YYYY-MM-DD'),'') || '|' ||
    coalesce(NEW.delivery_mode::text,'') || '|' ||
    coalesce(NEW.location,'') || '|' ||
    coalesce(NEW.tuition_fee::text,'') || '|' ||
    coalesce(NEW.currency,'') || '|' ||
    coalesce(NEW.url,'') || '|' ||
    coalesce(to_char(NEW.application_deadline,'YYYY-MM-DD'),'') || '|' ||
    coalesce(NEW.semester_or_acadyr,'') || '|' ||
    coalesce(NEW.timezone,'') || '|' ||
    coalesce(NEW.notes,'')
  );
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.compute_offering_variant_sig() OWNER TO mac;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: contact_info; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.contact_info (
    contact_id bigint NOT NULL,
    course_id bigint,
    offering_id bigint,
    email text,
    phone text,
    website text,
    note text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.contact_info OWNER TO mac;

--
-- Name: contact_info_contact_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.contact_info_contact_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.contact_info_contact_id_seq OWNER TO mac;

--
-- Name: contact_info_contact_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.contact_info_contact_id_seq OWNED BY public.contact_info.contact_id;


--
-- Name: course; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.course (
    course_id bigint NOT NULL,
    provider_id bigint NOT NULL,
    faculty_id bigint,
    title text NOT NULL,
    field_of_study text,
    programme_type public.programme_type_enum,
    level public.level_enum,
    language_codes text[],
    ects_credits numeric(5,2),
    workload_hours integer,
    award_or_certificate text,
    description text,
    teaching_methods text,
    assessment_methods text,
    recommended_reading text,
    other_fields jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT course_ects_credits_check CHECK (((ects_credits IS NULL) OR (ects_credits >= (0)::numeric))),
    CONSTRAINT course_workload_hours_check CHECK (((workload_hours IS NULL) OR (workload_hours >= 0)))
);


ALTER TABLE public.course OWNER TO mac;

--
-- Name: course_course_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.course_course_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.course_course_id_seq OWNER TO mac;

--
-- Name: course_course_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.course_course_id_seq OWNED BY public.course.course_id;


--
-- Name: course_module; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.course_module (
    module_id bigint NOT NULL,
    course_id bigint NOT NULL,
    title text NOT NULL,
    description text,
    ord integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.course_module OWNER TO mac;

--
-- Name: course_module_module_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.course_module_module_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.course_module_module_id_seq OWNER TO mac;

--
-- Name: course_module_module_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.course_module_module_id_seq OWNED BY public.course_module.module_id;


--
-- Name: course_person; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.course_person (
    course_id bigint NOT NULL,
    person_id bigint NOT NULL,
    role_at_course text NOT NULL
);


ALTER TABLE public.course_person OWNER TO mac;

--
-- Name: course_prerequisite; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.course_prerequisite (
    prereq_id bigint NOT NULL,
    course_id bigint NOT NULL,
    prereq_course_id bigint,
    text text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.course_prerequisite OWNER TO mac;

--
-- Name: course_prerequisite_prereq_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.course_prerequisite_prereq_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.course_prerequisite_prereq_id_seq OWNER TO mac;

--
-- Name: course_prerequisite_prereq_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.course_prerequisite_prereq_id_seq OWNED BY public.course_prerequisite.prereq_id;


--
-- Name: course_skill; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.course_skill (
    course_id bigint NOT NULL,
    skill_id bigint NOT NULL,
    target_level text
);


ALTER TABLE public.course_skill OWNER TO mac;

--
-- Name: faculty; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.faculty (
    faculty_id bigint NOT NULL,
    provider_id bigint NOT NULL,
    name text NOT NULL,
    website text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.faculty OWNER TO mac;

--
-- Name: faculty_faculty_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.faculty_faculty_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.faculty_faculty_id_seq OWNER TO mac;

--
-- Name: faculty_faculty_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.faculty_faculty_id_seq OWNED BY public.faculty.faculty_id;


--
-- Name: offering; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.offering (
    offering_id bigint NOT NULL,
    course_id bigint NOT NULL,
    start_date date,
    end_date date,
    semester_or_acadyr text,
    delivery_mode public.delivery_mode_enum,
    location text,
    timezone text,
    tuition_fee numeric(10,2),
    currency character(3),
    scholarship_funding text,
    application_deadline date,
    number_of_places integer,
    url text,
    notes text,
    other_fields jsonb,
    created_at timestamp with time zone DEFAULT now(),
    variant_sig text,
    CONSTRAINT offering_currency_check CHECK (((currency IS NULL) OR (length(currency) = 3))),
    CONSTRAINT offering_number_of_places_check CHECK (((number_of_places IS NULL) OR (number_of_places >= 0))),
    CONSTRAINT offering_tuition_fee_check CHECK (((tuition_fee IS NULL) OR (tuition_fee >= (0)::numeric)))
);


ALTER TABLE public.offering OWNER TO mac;

--
-- Name: offering_offering_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.offering_offering_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.offering_offering_id_seq OWNER TO mac;

--
-- Name: offering_offering_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.offering_offering_id_seq OWNED BY public.offering.offering_id;


--
-- Name: person; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.person (
    person_id bigint NOT NULL,
    full_name text NOT NULL,
    email text,
    role text,
    affiliation text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.person OWNER TO mac;

--
-- Name: person_person_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.person_person_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.person_person_id_seq OWNER TO mac;

--
-- Name: person_person_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.person_person_id_seq OWNED BY public.person.person_id;


--
-- Name: provider; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.provider (
    provider_id bigint NOT NULL,
    name text NOT NULL,
    country_code character(2),
    website text,
    contact_email text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.provider OWNER TO mac;

--
-- Name: provider_provider_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.provider_provider_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.provider_provider_id_seq OWNER TO mac;

--
-- Name: provider_provider_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.provider_provider_id_seq OWNED BY public.provider.provider_id;


--
-- Name: session; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.session (
    session_id bigint NOT NULL,
    offering_id bigint NOT NULL,
    session_start timestamp with time zone,
    session_end timestamp with time zone,
    modality text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.session OWNER TO mac;

--
-- Name: session_session_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.session_session_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.session_session_id_seq OWNER TO mac;

--
-- Name: session_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.session_session_id_seq OWNED BY public.session.session_id;


--
-- Name: skill; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.skill (
    skill_id bigint NOT NULL,
    label text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.skill OWNER TO mac;

--
-- Name: skill_skill_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.skill_skill_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.skill_skill_id_seq OWNER TO mac;

--
-- Name: skill_skill_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.skill_skill_id_seq OWNED BY public.skill.skill_id;


--
-- Name: source_doc; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.source_doc (
    source_id bigint NOT NULL,
    provider_id bigint,
    url_or_path text,
    doc_type text,
    captured_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.source_doc OWNER TO mac;

--
-- Name: source_doc_source_id_seq; Type: SEQUENCE; Schema: public; Owner: mac
--

CREATE SEQUENCE public.source_doc_source_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.source_doc_source_id_seq OWNER TO mac;

--
-- Name: source_doc_source_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: mac
--

ALTER SEQUENCE public.source_doc_source_id_seq OWNED BY public.source_doc.source_id;


--
-- Name: source_link; Type: TABLE; Schema: public; Owner: mac
--

CREATE TABLE public.source_link (
    source_id bigint NOT NULL,
    entity_type text NOT NULL,
    entity_id bigint NOT NULL
);


ALTER TABLE public.source_link OWNER TO mac;

--
-- Name: contact_info contact_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.contact_info ALTER COLUMN contact_id SET DEFAULT nextval('public.contact_info_contact_id_seq'::regclass);


--
-- Name: course course_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course ALTER COLUMN course_id SET DEFAULT nextval('public.course_course_id_seq'::regclass);


--
-- Name: course_module module_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_module ALTER COLUMN module_id SET DEFAULT nextval('public.course_module_module_id_seq'::regclass);


--
-- Name: course_prerequisite prereq_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_prerequisite ALTER COLUMN prereq_id SET DEFAULT nextval('public.course_prerequisite_prereq_id_seq'::regclass);


--
-- Name: faculty faculty_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.faculty ALTER COLUMN faculty_id SET DEFAULT nextval('public.faculty_faculty_id_seq'::regclass);


--
-- Name: offering offering_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.offering ALTER COLUMN offering_id SET DEFAULT nextval('public.offering_offering_id_seq'::regclass);


--
-- Name: person person_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.person ALTER COLUMN person_id SET DEFAULT nextval('public.person_person_id_seq'::regclass);


--
-- Name: provider provider_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.provider ALTER COLUMN provider_id SET DEFAULT nextval('public.provider_provider_id_seq'::regclass);


--
-- Name: session session_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.session ALTER COLUMN session_id SET DEFAULT nextval('public.session_session_id_seq'::regclass);


--
-- Name: skill skill_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.skill ALTER COLUMN skill_id SET DEFAULT nextval('public.skill_skill_id_seq'::regclass);


--
-- Name: source_doc source_id; Type: DEFAULT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.source_doc ALTER COLUMN source_id SET DEFAULT nextval('public.source_doc_source_id_seq'::regclass);


--
-- Data for Name: contact_info; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.contact_info (contact_id, course_id, offering_id, email, phone, website, note, created_at) FROM stdin;
\.


--
-- Data for Name: course; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.course (course_id, provider_id, faculty_id, title, field_of_study, programme_type, level, language_codes, ects_credits, workload_hours, award_or_certificate, description, teaching_methods, assessment_methods, recommended_reading, other_fields, created_at) FROM stdin;
18	11	\N	Analyte extraction and quantification from marine samples via spectroscopic techniques	Analytical Chemistry / Marine Samples	Lifelong Learning	Professional	{EN}	3.00	24	\N	Basic analytical chemistry; sample preservation; spectroscopic techniques; data processing	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
19	11	\N	Scuba diving for scientific research in coastal waters	Scientific Diving / Marine Science	Lifelong Learning	Professional	{EN}	3.00	24	\N	Sampling and diving techniques; expedition planning; equipment maintenance	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
20	11	\N	Techniques for the maintenance in captivity of Pinnidae (Bivalves)	Aquaculture / Bivalves	Lifelong Learning	Professional	{EN}	3.00	24	\N	Bivalve biology; RAS systems; feed production; experiment setup	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
21	12	\N	Environmental scanning electron microscopy and associated techniques (EDS, EBSD)	Microscopy / Materials	Lifelong Learning	Professional	{EN}	\N	15	\N	ESEM introduction, EDS analysis, EBSD, in-situ deformation tests	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
22	13	\N	Applications of gas chromatography for the determination of fatty acids in fish and fish feed	Analytical Chemistry / Food Science	Lifelong Learning	Professional	{EN}	1.30	33	\N	Folch extraction; esterification to FAME; capillary GC quantification	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
23	13	\N	Fish feed and seafood quality control	Food Quality / Aquaculture	Lifelong Learning	Professional	{EN}	2.00	50	\N	Proximate composition analysis: moisture, ash, protein, fat	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
24	13	\N	Applications of molecular biology in fisheries and aquaculture	Molecular Biology / Aquaculture	Lifelong Learning	Professional	{EN}	2.00	50	\N	DNA extraction; gel electrophoresis; PCR; qPCR	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
25	14	\N	Preparation of corruption prevention programs and plans	Public Administration / Governance	Lifelong Learning	Professional	{EN}	2.00	8	\N	Situation analysis; programme hierarchy; environmental analysis; logical programme model	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
26	15	\N	Underwater cultural heritage as a tourist	Cultural Heritage / Tourism	Lifelong Learning	Professional	{EN}	\N	40	\N	Definitions; typology; best practices; site selection; business plan	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
27	15	\N	Lexicology and lexicography	Linguistics / Lexicography	Lifelong Learning	Professional	{EN}	\N	\N	\N	Word/compound definitions; polysemy; lexeme vs term; dictionaries; translation/adaptation	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
28	16	\N	Basic surveying and cadastral concepts complementary to legal property registration	Surveying / Cadastre / GIS	Lifelong Learning	Professional	{EN}	14.00	140	\N	Topography basics; instruments; maps; coordinates; UAV; GIS; open data	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
29	16	\N	Surveying, cadastre and GIS in the oil domain	Surveying / Cadastre / GIS	Lifelong Learning	Professional	{EN}	12.00	120	\N	Cadastre basics; INIS; case studies; geoportals; ArcGIS; projections; DB creation	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
30	16	\N	Acquisition, processing and representation of spatial data using modern surveying instruments	Geodesy / Spatial Data	Lifelong Learning	Professional	{EN}	3.00	24	\N	3D positioning; laser scanner; satellite systems; modern geodesy	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
31	17	\N	Artificial Intelligence (Bachelor in Informatics Engineering)	Computer Science	Bachelor	Bachelor	{PT,EN}	6.00	162	ECTS credits	Python programming; ML algorithms; supervised/unsupervised; model evaluation	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
32	18	\N	Graduate Certificate of Data Science	Data Science	Graduate Certificate	Postgraduate	{EN}	\N	\N	Graduate Certificate	\N	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
33	19	\N	Solar Energy Conversion and Application (Micro-credential)	Energy / Sustainability	Micro-credential	Continuing Education	{EN}	\N	\N	Micro-credential	\N	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
34	20	\N	CAS Data Analysis	Data Science	CAS	Continuing Education	{DE,EN}	12.00	\N	CAS Certificate	Statistics with R; inference; regression; clustering & classification	\N	\N	\N	\N	2025-10-06 17:45:44.082503+02
\.


--
-- Data for Name: course_module; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.course_module (module_id, course_id, title, description, ord, created_at) FROM stdin;
\.


--
-- Data for Name: course_person; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.course_person (course_id, person_id, role_at_course) FROM stdin;
31	5	Coordinator
31	6	Lecturer
21	7	Lecturer
29	8	Lecturer
\.


--
-- Data for Name: course_prerequisite; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.course_prerequisite (prereq_id, course_id, prereq_course_id, text, created_at) FROM stdin;
\.


--
-- Data for Name: course_skill; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.course_skill (course_id, skill_id, target_level) FROM stdin;
\.


--
-- Data for Name: faculty; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.faculty (faculty_id, provider_id, name, website, created_at) FROM stdin;
\.


--
-- Data for Name: offering; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.offering (offering_id, course_id, start_date, end_date, semester_or_acadyr, delivery_mode, location, timezone, tuition_fee, currency, scholarship_funding, application_deadline, number_of_places, url, notes, other_fields, created_at, variant_sig) FROM stdin;
20	18	\N	\N	\N	on-site	Valencia, Spain	\N	350.00	EUR	\N	\N	\N	\N	24h; 3 ECTS	\N	2025-10-06 17:45:44.082503+02	b98cae36270f3d1dd9973aad7d14d22e
21	19	\N	\N	\N	on-site	Valencia, Spain	\N	300.00	EUR	\N	\N	\N	\N	24h; 3 ECTS	\N	2025-10-06 17:45:44.082503+02	fb3ca7de6e804bd1b6e1f71c870e9466
22	20	\N	\N	\N	on-site	Valencia, Spain	\N	250.00	EUR	\N	\N	\N	\N	24h; 3 ECTS	\N	2025-10-06 17:45:44.082503+02	d8cd1c27d8ce4b0c58bea58ac66c2e43
23	21	\N	\N	\N	blended	La Rochelle, France	\N	247.00	EUR	\N	\N	\N	\N	15h blended	\N	2025-10-06 17:45:44.082503+02	d2640bd3b89d34092df16f9f3a9b7624
24	22	\N	\N	\N	blended	Athens, Greece	\N	100.00	EUR	\N	\N	\N	\N	33h; 1.3 ECTS	\N	2025-10-06 17:45:44.082503+02	6b9c85365642def37561f55acd9f3ece
25	23	\N	\N	\N	blended	Athens, Greece	\N	150.00	EUR	\N	\N	\N	\N	50h; 2 ECTS	\N	2025-10-06 17:45:44.082503+02	d0beb9c80ddb80b7de0fe392a8de55e7
26	24	\N	\N	\N	blended	Athens, Greece	\N	200.00	EUR	\N	\N	\N	\N	50h; 2 ECTS	\N	2025-10-06 17:45:44.082503+02	ba97178a32e1acbc78f2506aa7a3add2
27	25	\N	\N	\N	blended	Klaipeda, Lithuania	\N	500.00	EUR	\N	\N	\N	\N	8h; 2 ECTS	\N	2025-10-06 17:45:44.082503+02	32b14f8c2a9a7effc56673b5401e816b
28	26	\N	\N	\N	online	Zadar, Croatia	\N	100.00	EUR	\N	\N	\N	\N	Online variant	\N	2025-10-06 17:45:44.082503+02	274b3cd467f420fd52d546bab31655bb
29	26	\N	\N	\N	on-site	Zadar, Croatia	\N	350.00	EUR	\N	\N	\N	\N	On-site variant	\N	2025-10-06 17:45:44.082503+02	0156e56cd6624cba04c1efd2a011bc72
30	27	\N	\N	\N	online	Zadar, Croatia	\N	150.00	EUR	\N	\N	\N	\N	Online variant	\N	2025-10-06 17:45:44.082503+02	98ac12b1236d95cc774a75a2d8400b7e
31	27	\N	\N	\N	on-site	Zadar, Croatia	\N	150.00	EUR	\N	\N	\N	\N	On-site variant	\N	2025-10-06 17:45:44.082503+02	fb7ed6d81d33acc9e0890b1e19f2fc23
32	28	\N	\N	\N	online	Bucharest, Romania	\N	300.00	EUR	\N	\N	\N	\N	Online/Blended options	\N	2025-10-06 17:45:44.082503+02	241f475e3f3d8500d3d15e28db8348aa
33	29	\N	\N	\N	online	Bucharest, Romania	\N	330.00	EUR	\N	\N	\N	\N	Online/Blended options	\N	2025-10-06 17:45:44.082503+02	0908fec6b270e1fc1f0d86b0bdbccceb
34	30	\N	\N	\N	on-site	Bucharest, Romania	\N	250.00	EUR	\N	\N	\N	\N	On-site	\N	2025-10-06 17:45:44.082503+02	233b55820ad0e8ffd9ab13d8bebc6d7a
35	31	2024-09-15	2025-01-15	Semester 1, 2024/2025	on-site	Bragança, Portugal	\N	\N	\N	\N	\N	\N	\N	ECTS 6; workload 162h	\N	2025-10-06 17:45:44.082503+02	fe5ce13c62f959ced33893c6df0626aa
36	32	\N	\N	\N	online	Melbourne, Australia	\N	\N	\N	\N	\N	\N	https://www.swinburne.edu.au/course/postgraduate/graduate-certificate-of-data-science/	Graduate Certificate	\N	2025-10-06 17:45:44.082503+02	1fd2399f2db30b262a5145c20c0c7953
37	33	\N	\N	\N	online	Dublin, Ireland	\N	\N	\N	\N	\N	\N	https://www.tcd.ie/courses/microcredentials/	Micro-credential	\N	2025-10-06 17:45:44.082503+02	a2318851e242408eada044c827d520ae
38	34	\N	\N	\N	on-site	Zurich, Switzerland	\N	7500.00	CHF	\N	2024-08-31	\N	\N	Part-time (weekly 9–17h); 12 ECTS	\N	2025-10-06 17:45:44.082503+02	6244a5a8084a842dc1264ff9fc3ccc31
\.


--
-- Data for Name: person; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.person (person_id, full_name, email, role, affiliation, created_at) FROM stdin;
5	Paulo Duarte Ferreira Gouveia	paulo.gouveia@ipb.pt	Course Coordinator	IPB	2025-10-06 17:45:44.082503+02
6	Jose Paulo Machado Da Costa	\N	Lecturer	IPB	2025-10-06 17:45:44.082503+02
7	Egle Conforto	egle.conforto@univ-lr.fr	Lecturer	La Rochelle Université	2025-10-06 17:45:44.082503+02
8	Ana Badea	ana.badea@utcb.ro	Lecturer	UTCB	2025-10-06 17:45:44.082503+02
\.


--
-- Data for Name: provider; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.provider (provider_id, name, country_code, website, contact_email, created_at) FROM stdin;
11	Catholic University of Valencia (IMEDMAR)	ES	https://www.ucv.es	imedmar@ucv.es	2025-10-06 17:45:44.082503+02
12	La Rochelle Université	FR	\N	egle.conforto@univ-lr.fr	2025-10-06 17:45:44.082503+02
13	Agricultural University of Athens	GR	https://www.aua.gr	echatzoglou@aua.gr	2025-10-06 17:45:44.082503+02
14	Klaipeda University	LT	https://www.ku.lt	jaroslav.dvorak@ku.lt	2025-10-06 17:45:44.082503+02
15	University of Zadar	HR	https://www.unizd.hr	irradic@unizd.hr	2025-10-06 17:45:44.082503+02
16	Technical University of Civil Engineering of Bucharest	RO	https://www.utcb.ro	ana.badea@utcb.ro	2025-10-06 17:45:44.082503+02
17	IPB - School of Technology and Management	PT	https://www.ipb.pt	\N	2025-10-06 17:45:44.082503+02
18	Swinburne University of Technology	AU	https://www.swinburne.edu.au	\N	2025-10-06 17:45:44.082503+02
19	Trinity College Dublin	IE	https://www.tcd.ie	\N	2025-10-06 17:45:44.082503+02
20	ZHAW School of Engineering	CH	https://www.zhaw.ch/engineering/weiterbildung	weiterbildung.engineering@zhaw.ch	2025-10-06 17:45:44.082503+02
\.


--
-- Data for Name: session; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.session (session_id, offering_id, session_start, session_end, modality, created_at) FROM stdin;
\.


--
-- Data for Name: skill; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.skill (skill_id, label, description, created_at) FROM stdin;
\.


--
-- Data for Name: source_doc; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.source_doc (source_id, provider_id, url_or_path, doc_type, captured_at) FROM stdin;
\.


--
-- Data for Name: source_link; Type: TABLE DATA; Schema: public; Owner: mac
--

COPY public.source_link (source_id, entity_type, entity_id) FROM stdin;
\.


--
-- Name: contact_info_contact_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.contact_info_contact_id_seq', 1, false);


--
-- Name: course_course_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.course_course_id_seq', 34, true);


--
-- Name: course_module_module_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.course_module_module_id_seq', 1, false);


--
-- Name: course_prerequisite_prereq_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.course_prerequisite_prereq_id_seq', 1, false);


--
-- Name: faculty_faculty_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.faculty_faculty_id_seq', 1, false);


--
-- Name: offering_offering_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.offering_offering_id_seq', 38, true);


--
-- Name: person_person_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.person_person_id_seq', 8, true);


--
-- Name: provider_provider_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.provider_provider_id_seq', 20, true);


--
-- Name: session_session_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.session_session_id_seq', 1, false);


--
-- Name: skill_skill_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.skill_skill_id_seq', 1, false);


--
-- Name: source_doc_source_id_seq; Type: SEQUENCE SET; Schema: public; Owner: mac
--

SELECT pg_catalog.setval('public.source_doc_source_id_seq', 1, false);


--
-- Name: contact_info contact_info_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.contact_info
    ADD CONSTRAINT contact_info_pkey PRIMARY KEY (contact_id);


--
-- Name: course_module course_module_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_module
    ADD CONSTRAINT course_module_pkey PRIMARY KEY (module_id);


--
-- Name: course_person course_person_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_person
    ADD CONSTRAINT course_person_pkey PRIMARY KEY (course_id, person_id, role_at_course);


--
-- Name: course course_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_pkey PRIMARY KEY (course_id);


--
-- Name: course_prerequisite course_prerequisite_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_prerequisite
    ADD CONSTRAINT course_prerequisite_pkey PRIMARY KEY (prereq_id);


--
-- Name: course course_provider_id_title_programme_type_key; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_provider_id_title_programme_type_key UNIQUE (provider_id, title, programme_type);


--
-- Name: course_skill course_skill_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_skill
    ADD CONSTRAINT course_skill_pkey PRIMARY KEY (course_id, skill_id);


--
-- Name: faculty faculty_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.faculty
    ADD CONSTRAINT faculty_pkey PRIMARY KEY (faculty_id);


--
-- Name: faculty faculty_provider_id_name_key; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.faculty
    ADD CONSTRAINT faculty_provider_id_name_key UNIQUE (provider_id, name);


--
-- Name: offering offering_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.offering
    ADD CONSTRAINT offering_pkey PRIMARY KEY (offering_id);


--
-- Name: person person_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.person
    ADD CONSTRAINT person_pkey PRIMARY KEY (person_id);


--
-- Name: provider provider_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.provider
    ADD CONSTRAINT provider_pkey PRIMARY KEY (provider_id);


--
-- Name: session session_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.session
    ADD CONSTRAINT session_pkey PRIMARY KEY (session_id);


--
-- Name: skill skill_label_key; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.skill
    ADD CONSTRAINT skill_label_key UNIQUE (label);


--
-- Name: skill skill_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.skill
    ADD CONSTRAINT skill_pkey PRIMARY KEY (skill_id);


--
-- Name: source_doc source_doc_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.source_doc
    ADD CONSTRAINT source_doc_pkey PRIMARY KEY (source_id);


--
-- Name: source_link source_link_pkey; Type: CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.source_link
    ADD CONSTRAINT source_link_pkey PRIMARY KEY (source_id, entity_type, entity_id);


--
-- Name: idx_course_title_trgm; Type: INDEX; Schema: public; Owner: mac
--

CREATE INDEX idx_course_title_trgm ON public.course USING gin (title public.gin_trgm_ops);


--
-- Name: idx_offering_dates; Type: INDEX; Schema: public; Owner: mac
--

CREATE INDEX idx_offering_dates ON public.offering USING btree (start_date, end_date);


--
-- Name: idx_offering_fee; Type: INDEX; Schema: public; Owner: mac
--

CREATE INDEX idx_offering_fee ON public.offering USING btree (currency, tuition_fee);


--
-- Name: idx_person_email; Type: INDEX; Schema: public; Owner: mac
--

CREATE INDEX idx_person_email ON public.person USING btree (email);


--
-- Name: uq_offering_variant; Type: INDEX; Schema: public; Owner: mac
--

CREATE UNIQUE INDEX uq_offering_variant ON public.offering USING btree (course_id, variant_sig);


--
-- Name: uq_person_name_email; Type: INDEX; Schema: public; Owner: mac
--

CREATE UNIQUE INDEX uq_person_name_email ON public.person USING btree (full_name, COALESCE(email, ''::text));


--
-- Name: offering trg_offering_variant_sig; Type: TRIGGER; Schema: public; Owner: mac
--

CREATE TRIGGER trg_offering_variant_sig BEFORE INSERT OR UPDATE ON public.offering FOR EACH ROW EXECUTE FUNCTION public.compute_offering_variant_sig();


--
-- Name: contact_info contact_info_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.contact_info
    ADD CONSTRAINT contact_info_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(course_id) ON DELETE CASCADE;


--
-- Name: contact_info contact_info_offering_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.contact_info
    ADD CONSTRAINT contact_info_offering_id_fkey FOREIGN KEY (offering_id) REFERENCES public.offering(offering_id) ON DELETE CASCADE;


--
-- Name: course course_faculty_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_faculty_id_fkey FOREIGN KEY (faculty_id) REFERENCES public.faculty(faculty_id) ON DELETE SET NULL;


--
-- Name: course_module course_module_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_module
    ADD CONSTRAINT course_module_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(course_id) ON DELETE CASCADE;


--
-- Name: course_person course_person_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_person
    ADD CONSTRAINT course_person_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(course_id) ON DELETE CASCADE;


--
-- Name: course_person course_person_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_person
    ADD CONSTRAINT course_person_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.person(person_id) ON DELETE CASCADE;


--
-- Name: course_prerequisite course_prerequisite_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_prerequisite
    ADD CONSTRAINT course_prerequisite_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(course_id) ON DELETE CASCADE;


--
-- Name: course_prerequisite course_prerequisite_prereq_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_prerequisite
    ADD CONSTRAINT course_prerequisite_prereq_course_id_fkey FOREIGN KEY (prereq_course_id) REFERENCES public.course(course_id) ON DELETE SET NULL;


--
-- Name: course course_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.provider(provider_id) ON DELETE CASCADE;


--
-- Name: course_skill course_skill_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_skill
    ADD CONSTRAINT course_skill_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(course_id) ON DELETE CASCADE;


--
-- Name: course_skill course_skill_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.course_skill
    ADD CONSTRAINT course_skill_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skill(skill_id) ON DELETE CASCADE;


--
-- Name: faculty faculty_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.faculty
    ADD CONSTRAINT faculty_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.provider(provider_id) ON DELETE CASCADE;


--
-- Name: offering offering_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.offering
    ADD CONSTRAINT offering_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(course_id) ON DELETE CASCADE;


--
-- Name: session session_offering_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.session
    ADD CONSTRAINT session_offering_id_fkey FOREIGN KEY (offering_id) REFERENCES public.offering(offering_id) ON DELETE CASCADE;


--
-- Name: source_doc source_doc_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.source_doc
    ADD CONSTRAINT source_doc_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.provider(provider_id) ON DELETE SET NULL;


--
-- Name: source_link source_link_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mac
--

ALTER TABLE ONLY public.source_link
    ADD CONSTRAINT source_link_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.source_doc(source_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict hIJudC3OqVAvzzyuIUzf6KifGnBcSIlmVgpYiae8IBukGc1JoGeGpkMQnrwZEyA

