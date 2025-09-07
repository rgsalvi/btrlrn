# syllabus_db.py
import sqlite3
DB_PATH = 'mvp.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS syllabus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board TEXT,
            grade INTEGER,
            subject TEXT,
            academic_year TEXT,
            topic TEXT,
            description TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_syllabus(board, grade, subject, academic_year, topic, description):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO syllabus (board, grade, subject, academic_year, topic, description)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (board, grade, subject, academic_year, topic, description))
    conn.commit()
    conn.close()

def get_syllabus(board, grade, subject, academic_year):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT topic, description FROM syllabus
        WHERE board=? AND grade=? AND subject=? AND academic_year=?
    ''', (board, grade, subject, academic_year))
    results = cur.fetchall()
    conn.close()
    return results

if __name__ == '__main__':
    init_db()

    board = 'CBSE'
    academic_year = '2025-26'

    # Syllabus topics for Grades 6 to 12
    syllabus_data = {
        6: {
            'Marathi': [
                'आम्ही सारे सरदार', 'शाळा', 'माझे कुटुंब', 'माझे गाव', 'माझे छंद', 'माझे आवडते फळ', 'माझा आवडता प्राणी', 'माझा आवडता खेळ', 'माझा आवडता सण', 'माझा आवडता ऋतू', 'माझा आवडता मित्र', 'माझा आवडता शिक्षक', 'माझे स्वप्न', 'माझा भारत देश', 'माझे शाळेतील जीवन', 'माझे आवडते पुस्तक', 'माझा आवडता नेता', 'माझा आवडता कवी', 'माझा आवडता लेखक', 'माझा आवडता क्रीडापटू'
            ],
            'Hindi': [
                'हमारा देश', 'मेरा परिवार', 'मेरा विद्यालय', 'मेरा मित्र', 'मेरा प्रिय खेल', 'मेरा प्रिय त्योहार', 'मेरा प्रिय फल', 'मेरा प्रिय जानवर', 'मेरा प्रिय ऋतु', 'मेरा प्रिय शिक्षक', 'मेरा सपना', 'मेरा भारत', 'मेरा शौक', 'मेरा प्रिय पुस्तक', 'मेरा प्रिय नेता', 'मेरा प्रिय कवि', 'मेरा प्रिय लेखक', 'मेरा प्रिय क्रीड़ापटु'
            ],
            'English': [
                "Don't Give Up!", "Who's the Greatest?", "The Worth of a Fabric", "The Phantom Dog", "The King's Choice", "The Silver House", "The Never-Never Nest", "The Road Not Taken", "The Story of Gautama's Quest", "The Value of Time", "The Power of Determination", "The World of Plants", "The World of Animals", "The World of Birds", "The World of Insects"
            ],
            'Mathematics': [
                'Basic Concepts in Geometry', 'Integers', 'Fractions', 'Decimals', 'Ratio and Proportion', 'Algebraic Expressions', 'Mensuration', 'Data Handling', 'Symmetry', 'Practical Geometry', 'Playing with Numbers', 'Understanding Elementary Shapes', 'Whole Numbers', 'Knowing Our Numbers'
            ],
            'Science and Technology': [
                'Our Earth and Our Solar System', 'The Living World', 'Diversity in Living Things', 'Substances in the Surroundings', 'Changes Around Us', 'Measurement and Motion', 'Energy', 'Simple Machines', 'The Environment', 'Food and Nutrition', 'Health and Hygiene', 'Materials and Solutions', 'Natural Resources', 'Our Universe'
            ],
            'History and Civics': [
                'The Indian Subcontinent and History', 'Sources of History', 'The Harappan Civilization', 'The Vedic Civilization', 'Religious Trends in Ancient India', 'Janapadas and Mahajanapadas', 'The First Empire of India: The Mauryas', 'The Age of Regional Kingdoms', 'The Gupta Age', 'The Age of Small Kingdoms', 'The Cholas', 'The Delhi Sultanate', 'The Mughal Empire', 'The Maratha Empire', 'The British Rule in India', 'The Freedom Struggle', 'Civics: Our Constitution', 'Civics: Local Government', 'Civics: Our Rights and Duties'
            ],
            'Geography': [
                'The Earth and the Graticule', 'Let us Use the Graticule', 'Comparing a Globe and a Map', 'Field Visits', 'Weather and Climate', 'The Structure of the Earth', 'The Sun, the Moon and the Earth', 'The Motions of the Earth', 'The Interior of the Earth', 'Rocks and Soils', 'Natural Regions', 'Population', 'Natural Resources', 'Conservation of Resources', 'Disaster Management'
            ]
        },
        7: {
            'English': [
                'Three Questions', 'A Gift of Chappals', 'Gopal and the Hilsa Fish', 'The Ashes That Made Trees Bloom', 'Quality', 'Expert Detectives', 'The Invention of Vita-Wonk', 'Fire: Friend and Foe', 'A Bicycle in Good Repair', 'The Story of Cricket', 'Garden Snake', 'Chivvy', 'Trees', 'Mystery of the Talking Fan', 'Dad and the Cat and the Tree', 'Meadow Surprises', 'The Shed', 'The Rebel', 'The Bear Story', 'A Tiger in the House', 'An Alien Hand', 'The Desert', 'The Cop and the Anthem'
            ],
            'Hindi': [
                'हम पंछी उन्मुक्त गगन के', 'दादी माँ', 'हिमालय की बेटियाँ', 'कुत्ता', 'माँ', 'एक तिनका', 'खुशबू रचते हैं हाथ', 'काबुलीवाला', 'आषाढ़ का पहला दिन', 'वर्षा ऋतु', 'नौकर', 'सपनों के-से दिन', 'शहीद झलकारी बाई', 'बालगोबिन भगत', 'पर्वत', 'मेरा जीवन', 'सूर्य', 'पानी', 'कविता की आत्मा', 'कविता का उद्देश्य'
            ],
            'Mathematics': [
                'Integers', 'Fractions and Decimals', 'Data Handling', 'Simple Equations', 'Lines and Angles', 'The Triangle and its Properties', 'Congruence of Triangles', 'Comparing Quantities', 'Rational Numbers', 'Practical Geometry', 'Perimeter and Area', 'Algebraic Expressions', 'Exponents and Powers', 'Symmetry', 'Visualising Solid Shapes'
            ],
            'Science': [
                'Nutrition in Plants', 'Nutrition in Animals', 'Fibre to Fabric', 'Heat', 'Acids, Bases and Salts', 'Physical and Chemical Changes', 'Weather, Climate and Adaptations of Animals to Climate', 'Winds, Storms and Cyclones', 'Soil', 'Respiration in Organisms', 'Transportation in Animals and Plants', 'Reproduction in Plants', 'Motion and Time', 'Electric Current and its Effects', 'Light', 'Water: A Precious Resource', 'Forests: Our Lifeline', 'Wastewater Story'
            ],
            'History': [
                'Tracing Changes Through a Thousand Years', 'New Kings and Kingdoms', 'The Delhi Sultans', 'The Mughal Empire', 'Rulers and Buildings', 'Towns, Traders and Craftspersons', 'Tribes, Nomads and Settled Communities', 'Devotional Paths to the Divine', 'The Making of Regional Cultures', 'Eighteenth-Century Political Formations'
            ],
            'Geography': [
                'Environment', 'Inside Our Earth', 'Our Changing Earth', 'Air', 'Water', 'Natural Vegetation and Wildlife', 'Human Environment – Settlement, Transport and Communication', 'Human Environment Interactions – The Tropical and the Subtropical Region', 'Life in the Deserts'
            ],
            'Civics': [
                'On Equality', 'Role of the Government in Health', 'How the State Government Works', 'Growing up as Boys and Girls', 'Women Change the World', 'Understanding Media', 'Understanding Advertising', 'Markets Around Us', 'A Shirt in the Market', 'Struggles for Equality'
            ],
            'Sanskrit': [
                'सुभाषितानि', 'धातुपाठः', 'स्वर्णकाकः', 'क्रीडास्पर्धा', 'अहं बालकः', 'मम विद्यालयः', 'कृषकः', 'बालकः', 'सूक्तिः', 'कस्मै धेनुः'
            ],
            'Computer Science': [
                'Computer Software', 'Number System', 'Introduction to MS Word', 'Introduction to MS Excel', 'Internet and its Uses', 'Introduction to MS PowerPoint', 'Cyber Safety'
            ]
        },
        8: {
            'English': [
                'The Best Christmas Present in the World', 'The Tsunami', 'Glimpses of the Past', 'Bepin Choudhury’s Lapse of Memory', 'The Summit Within', 'This is Jody’s Fawn', 'A Visit to Cambridge', 'A Short Monsoon Diary', 'The Great Stone Face – I', 'The Great Stone Face – II', 'The Ant and the Cricket', 'Geography Lesson', 'Macavity: The Mystery Cat', 'The Last Bargain', 'The School Boy', 'The Duck and the Kangaroo', 'When I set out for Lyonnesse', 'The Spider and the Fly', 'The Selfish Giant', 'The Treasure Within', 'Princess September', 'The Fight', 'The Open Window', 'Jalebis', 'The Comet – I', 'The Comet – II'
            ],
            'Hindi': [
                'ध्वनि', 'लाख की चूड़ियाँ', 'बस की यात्रा', 'दीवानों की हस्ती', 'चिट्ठियों की अनूठी दुनिया', 'भूतनाथ', 'संविधान', 'संकल्प', 'सपनों के-से दिन', 'शहीद झलकारी बाई', 'बालगोबिन भगत', 'पर्वत', 'मेरा जीवन', 'सूर्य', 'पानी', 'कविता की आत्मा', 'कविता का उद्देश्य'
            ],
            'Mathematics': [
                'Rational Numbers', 'Linear Equations in One Variable', 'Understanding Quadrilaterals', 'Practical Geometry', 'Data Handling', 'Squares and Square Roots', 'Cubes and Cube Roots', 'Comparing Quantities', 'Algebraic Expressions and Identities', 'Mensuration', 'Exponents and Powers', 'Direct and Inverse Proportions', 'Factorisation', 'Introduction to Graphs', 'Playing with Numbers'
            ],
            'Science': [
                'Crop Production and Management', 'Microorganisms: Friend and Foe', 'Synthetic Fibres and Plastics', 'Materials: Metals and Non-Metals', 'Coal and Petroleum', 'Combustion and Flame', 'Conservation of Plants and Animals', 'Cell – Structure and Functions', 'Reproduction in Animals', 'Reaching the Age of Adolescence', 'Force and Pressure', 'Friction', 'Sound', 'Chemical Effects of Electric Current', 'Some Natural Phenomena', 'Light', 'Stars and the Solar System', 'Pollution of Air and Water'
            ],
            'History': [
                'How, When and Where', 'From Trade to Territory', 'Ruling the Countryside', 'Tribes, Castes and Communities', 'Crafts and Industries', 'Civilising the "Native", Educating the Nation', 'Women, Caste and Reform', 'The Making of the National Movement: 1870s–1947', 'India After Independence'
            ],
            'Geography': [
                'Resources', 'Land, Soil, Water, Natural Vegetation and Wildlife Resources', 'Mineral and Power Resources', 'Agriculture', 'Industries', 'Human Resources'
            ],
            'Civics': [
                'The Indian Constitution', 'Understanding Secularism', 'Why Do We Need a Parliament?', 'Understanding Laws', 'Judiciary', 'Understanding Our Criminal Justice System', 'Social Justice and the Marginalised', 'Confronting Marginalisation', 'Public Facilities', 'Law and Social Justice'
            ],
            'Sanskrit': [
                'सुभाषितानि', 'धातुपाठः', 'स्वर्णकाकः', 'क्रीडास्पर्धा', 'अहं बालकः', 'मम विद्यालयः', 'कृषकः', 'बालकः', 'सूक्तिः', 'कस्मै धेनुः'
            ],
            'Computer Science': [
                'Introduction to Database', 'Introduction to HTML', 'Introduction to QBasic', 'Networking Concepts', 'Cyber Safety', 'MS Access', 'MS PowerPoint Advanced'
            ]
        },
        9: {
            'English': [
                'The Fun They Had', 'The Sound of Music', 'The Little Girl', 'A Truly Beautiful Mind', 'The Snake and the Mirror', 'My Childhood', 'Packing', 'Reach for the Top', 'The Bond of Love', 'Kathmandu', 'If I Were You', 'The Road Not Taken', 'Wind', 'Rain on the Roof', 'The Lake Isle of Innisfree', 'A Legend of the Northland', 'No Men Are Foreign', 'On Killing a Tree', 'The Snake Trying', 'A Slumber Did My Spirit Seal'
            ],
            'Hindi': [
                'दो बैलों की कथा', 'ल्हासा की ओर', 'मेरे संग की औरतें', 'रेगिस्तान', 'साखियाँ', 'वाख', 'सवाने', 'कविता की आत्मा', 'कविता का उद्देश्य', 'पानी', 'सूर्य', 'मेरा जीवन', 'पर्वत', 'बालगोबिन भगत', 'शहीद झलकारी बाई', 'सपनों के-से दिन'
            ],
            'Mathematics': [
                'Number Systems', 'Polynomials', 'Coordinate Geometry', 'Linear Equations in Two Variables', 'Introduction to Euclid’s Geometry', 'Lines and Angles', 'Triangles', 'Quadrilaterals', 'Areas of Parallelograms and Triangles', 'Circles', 'Constructions', 'Heron’s Formula', 'Surface Areas and Volumes', 'Statistics', 'Probability'
            ],
            'Science': [
                'Matter in Our Surroundings', 'Is Matter Around Us Pure?', 'Atoms and Molecules', 'Structure of the Atom', 'The Fundamental Unit of Life', 'Tissues', 'Diversity in Living Organisms', 'Motion', 'Force and Laws of Motion', 'Gravitation', 'Work and Energy', 'Sound', 'Why Do We Fall Ill?', 'Natural Resources', 'Improvement in Food Resources'
            ],
            'History': [
                'The French Revolution', 'Socialism in Europe and the Russian Revolution', 'Nazism and the Rise of Hitler', 'Forest Society and Colonialism', 'Pastoralists in the Modern World', 'Peasants and Farmers', 'History and Sport: The Story of Cricket', 'Clothing: A Social History'
            ],
            'Geography': [
                'India – Size and Location', 'Physical Features of India', 'Drainage', 'Climate', 'Natural Vegetation and Wildlife', 'Population'
            ],
            'Civics': [
                'What is Democracy? Why Democracy?', 'Constitutional Design', 'Electoral Politics', 'Working of Institutions', 'Democratic Rights'
            ],
            'Sanskrit': [
                'सुभाषितानि', 'धातुपाठः', 'स्वर्णकाकः', 'क्रीडास्पर्धा', 'अहं बालकः', 'मम विद्यालयः', 'कृषकः', 'बालकः', 'सूक्तिः', 'कस्मै धेनुः'
            ],
            'Computer Science': [
                'Introduction to Computers', 'Operating System', 'Office Tools', 'Internet Basics', 'HTML Basics', 'Cyber Safety', 'Database Concepts'
            ]
        },
        10: {
            'English': [
                'A Letter to God', 'Nelson Mandela: Long Walk to Freedom', 'Two Stories about Flying', 'From the Diary of Anne Frank', 'The Hundred Dresses – I', 'The Hundred Dresses – II', 'Glimpses of India', 'Mijbil the Otter', 'Madam Rides the Bus', 'The Sermon at Benares', 'The Proposal', 'Dust of Snow', 'Fire and Ice', 'A Tiger in the Zoo', 'How to Tell Wild Animals', 'The Ball Poem', 'Amanda!', 'Animals', 'The Trees', 'Fog', 'The Tale of Custard the Dragon', 'For Anne Gregory'
            ],
            'Hindi': [
                'साखियाँ', 'वाख', 'सवाने', 'कविता की आत्मा', 'कविता का उद्देश्य', 'पानी', 'सूर्य', 'मेरा जीवन', 'पर्वत', 'बालगोबिन भगत', 'शहीद झलकारी बाई', 'सपनों के-से दिन', 'दो बैलों की कथा', 'ल्हासा की ओर', 'मेरे संग की औरतें', 'रेगिस्तान'
            ],
            'Mathematics': [
                'Real Numbers', 'Polynomials', 'Pair of Linear Equations in Two Variables', 'Quadratic Equations', 'Arithmetic Progressions', 'Triangles', 'Coordinate Geometry', 'Introduction to Trigonometry', 'Circles', 'Constructions', 'Areas Related to Circles', 'Surface Areas and Volumes', 'Statistics', 'Probability'
            ],
            'Science': [
                'Chemical Reactions and Equations', 'Acids, Bases and Salts', 'Metals and Non-metals', 'Carbon and its Compounds', 'Periodic Classification of Elements', 'Life Processes', 'Control and Coordination', 'How do Organisms Reproduce?', 'Heredity and Evolution', 'Light – Reflection and Refraction', 'The Human Eye and the Colourful World', 'Electricity', 'Magnetic Effects of Electric Current', 'Sources of Energy', 'Our Environment', 'Management of Natural Resources'
            ],
            'History': [
                'The Rise of Nationalism in Europe', 'Nationalism in India', 'The Making of a Global World', 'The Age of Industrialisation', 'Print Culture and the Modern World'
            ],
            'Geography': [
                'Resources and Development', 'Forest and Wildlife Resources', 'Water Resources', 'Agriculture', 'Minerals and Energy Resources', 'Manufacturing Industries', 'Lifelines of National Economy'
            ],
            'Civics': [
                'Power Sharing', 'Federalism', 'Democracy and Diversity', 'Gender, Religion and Caste', 'Popular Struggles and Movements', 'Political Parties', 'Outcomes of Democracy'
            ],
            'Sanskrit': [
                'सुभाषितानि', 'धातुपाठः', 'स्वर्णकाकः', 'क्रीडास्पर्धा', 'अहं बालकः', 'मम विद्यालयः', 'कृषकः', 'बालकः', 'सूक्तिः', 'कस्मै धेनुः'
            ],
            'Computer Science': [
                'Python Programming', 'Database Management', 'HTML Advanced', 'Networking Concepts', 'Cyber Safety', 'MS Office Advanced', 'Internet Applications'
            ]
        },
        11: {
            'English': [
                'The Portrait of a Lady', 'A Photograph', 'We’re Not Afraid to Die…', 'Discovering Tut: the Saga Continues', 'The Laburnum Top', 'Landscape of the Soul', 'The Voice of the Rain', 'The Ailing Planet: the Green Movement’s Role', 'The Browning Version', 'Childhood', 'Father to Son', 'Silk Road', 'Mother’s Day', 'Birth', 'The Adventure', 'The Summer of the Beautiful White Horse', 'The Address', 'Ranga’s Marriage', 'Albert Einstein at School', 'The Ghat of the Only World', 'The Tale of Melon City'
            ],
            'Hindi': [
                'आलोक धन्वा', 'कविता की आत्मा', 'कविता का उद्देश्य', 'पानी', 'सूर्य', 'मेरा जीवन', 'पर्वत', 'बालगोबिन भगत', 'शहीद झलकारी बाई', 'सपनों के-से दिन', 'दो बैलों की कथा', 'ल्हासा की ओर', 'मेरे संग की औरतें', 'रेगिस्तान'
            ],
            'Mathematics': [
                'Sets', 'Relations and Functions', 'Trigonometric Functions', 'Principle of Mathematical Induction', 'Complex Numbers and Quadratic Equations', 'Linear Inequalities', 'Permutations and Combinations', 'Binomial Theorem', 'Sequences and Series', 'Straight Lines', 'Conic Sections', 'Introduction to Three-dimensional Geometry', 'Limits and Derivatives', 'Mathematical Reasoning', 'Statistics', 'Probability'
            ],
            'Science': [
                'Physical World', 'Units and Measurements', 'Motion in a Straight Line', 'Motion in a Plane', 'Laws of Motion', 'Work, Energy and Power', 'System of Particles and Rotational Motion', 'Gravitation', 'Mechanical Properties of Solids', 'Mechanical Properties of Fluids', 'Thermal Properties of Matter', 'Thermodynamics', 'Kinetic Theory', 'Oscillations', 'Waves', 'Some Basic Concepts of Chemistry', 'Structure of Atom', 'Classification of Elements and Periodicity in Properties', 'Chemical Bonding and Molecular Structure', 'States of Matter', 'Thermodynamics', 'Equilibrium', 'Redox Reactions', 'Hydrogen', 's-Block Element', 'Some p-Block Elements', 'Environmental Chemistry', 'The Living World', 'Biological Classification', 'Plant Kingdom', 'Animal Kingdom', 'Morphology of Flowering Plants', 'Anatomy of Flowering Plants', 'Structural Organisation in Animals', 'Cell: The Unit of Life', 'Biomolecules', 'Cell Cycle and Cell Division', 'Transport in Plants', 'Mineral Nutrition', 'Photosynthesis in Higher Plants', 'Respiration in Plants', 'Plant Growth and Development', 'Digestion and Absorption', 'Breathing and Exchange of Gases', 'Body Fluids and Circulation', 'Excretory Products and their Elimination', 'Locomotion and Movement', 'Neural Control and Coordination', 'Chemical Coordination and Integration'
            ],
            'History': [
                'From the Beginning of Time', 'Writing and City Life', 'An Empire Across Three Continents', 'The Central Islamic Lands', 'Nomadic Empires', 'The Three Orders', 'Changing Cultural Traditions', 'Confrontation of Cultures', 'The Industrial Revolution', 'Displacing Indigenous Peoples', 'Paths to Modernisation'
            ],
            'Geography': [
                'Geography as a Discipline', 'The Earth’s Interior', 'Landforms', 'Climate', 'Water (Oceans)', 'Life on the Earth', 'India: Physical Features', 'India: Climate', 'India: Natural Vegetation', 'India: Wildlife', 'India: Soils', 'India: Water Resources', 'India: Mineral and Energy Resources', 'India: Agriculture', 'India: Industries', 'India: Transport and Communication', 'India: International Trade'
            ],
            'Civics': [
                'Indian Constitution at Work', 'Rights in the Indian Constitution', 'Election and Representation', 'Executive', 'Legislature', 'Judiciary', 'Federalism', 'Local Governments', 'Constitution as a Living Document', 'Political Theory', 'Freedom', 'Equality', 'Social Justice', 'Rights', 'Citizenship', 'Nationalism', 'Secularism', 'Peace', 'Development'
            ],
            'Sanskrit': [
                'सुभाषितानि', 'धातुपाठः', 'स्वर्णकाकः', 'क्रीडास्पर्धा', 'अहं बालकः', 'मम विद्यालयः', 'कृषकः', 'बालकः', 'सूक्तिः', 'कस्मै धेनुः'
            ],
            'Computer Science': [
                'Python Programming', 'Database Management', 'HTML Advanced', 'Networking Concepts', 'Cyber Safety', 'MS Office Advanced', 'Internet Applications', 'C++ Basics', 'Java Basics'
            ]
        },
        12: {
            'English': [
                'The Last Lesson', 'Lost Spring', 'Deep Water', 'The Rattrap', 'Indigo', 'Poets and Pancakes', 'The Interview', 'Going Places', 'My Mother at Sixty-six', 'Keeping Quiet', 'A Thing of Beauty', 'A Roadside Stand', 'Aunt Jennifer’s Tigers', 'The Third Level', 'The Tiger King', 'Journey to the End of the Earth', 'The Enemy', 'On the Face of It', 'Evans Tries an O-Level', 'Memories of Childhood'
            ],
            'Hindi': [
                'आलोक धन्वा', 'कविता की आत्मा', 'कविता का उद्देश्य', 'पानी', 'सूर्य', 'मेरा जीवन', 'पर्वत', 'बालगोबिन भगत', 'शहीद झलकारी बाई', 'सपनों के-से दिन', 'दो बैलों की कथा', 'ल्हासा की ओर', 'मेरे संग की औरतें', 'रेगिस्तान'
            ],
            'Mathematics': [
                'Relations and Functions', 'Inverse Trigonometric Functions', 'Matrices', 'Determinants', 'Continuity and Differentiability', 'Application of Derivatives', 'Integrals', 'Application of Integrals', 'Differential Equations', 'Vector Algebra', 'Three-dimensional Geometry', 'Linear Programming', 'Probability'
            ],
            'Science': [
                'Reproduction in Organisms', 'Genetics and Evolution', 'Biology and Human Welfare', 'Biotechnology and its Applications', 'Ecology and Environment', 'Solid State', 'Solutions', 'Electrochemistry', 'Chemical Kinetics', 'Surface Chemistry', 'General Principles and Processes of Isolation of Elements', 'p-Block Elements', 'd and f Block Elements', 'Coordination Compounds', 'Haloalkanes and Haloarenes', 'Alcohols, Phenols and Ethers', 'Aldehydes, Ketones and Carboxylic Acids', 'Organic Compounds containing Nitrogen', 'Biomolecules', 'Polymers', 'Chemistry in Everyday Life', 'Electric Charges and Fields', 'Electrostatic Potential and Capacitance', 'Current Electricity', 'Magnetic Effects of Current and Magnetism', 'Electromagnetic Induction and Alternating Currents', 'Electromagnetic Waves', 'Optics', 'Dual Nature of Radiation and Matter', 'Atoms and Nuclei', 'Electronic Devices', 'Communication Systems'
            ],
            'History': [
                'Bricks, Beads and Bones', 'Kings, Farmers and Towns', 'Kinship, Caste and Class', 'Thinkers, Beliefs and Buildings', 'Through the Eyes of Travellers', 'Bhakti – Sufi Traditions', 'An Imperial Capital: Vijayanagara', 'Peasants, Zamindars and the State', 'Colonialism and the Countryside', 'Rebels and the Raj', 'Colonial Cities', 'Mahatma Gandhi and the Nationalist Movement', 'Understanding Partition', 'Framing the Constitution'
            ],
            'Geography': [
                'Human Geography: Nature and Scope', 'The World Population', 'Migration', 'Human Settlements', 'Resources and Development', 'Transport and Communication', 'International Trade', 'India: People and Economy', 'India: Human Settlements', 'India: Resources and Development', 'India: Transport and Communication', 'India: International Trade'
            ],
            'Civics': [
                'The End of Bipolarity', 'Contemporary Centres of Power', 'Contemporary South Asia', 'United Nations and its Organizations', 'Security in the Contemporary World', 'Environment and Natural Resources', 'Globalisation', 'Challenges of Nation Building', 'Era of One-Party Dominance', 'Politics of Planned Development', 'India’s External Relations', 'Challenges to the Congress System', 'Crisis of the Democratic Order', 'Rise of Popular Movements', 'Regional Aspirations', 'Recent Developments in Indian Politics'
            ],
            'Sanskrit': [
                'सुभाषितानि', 'धातुपाठः', 'स्वर्णकाकः', 'क्रीडास्पर्धा', 'अहं बालकः', 'मम विद्यालयः', 'कृषकः', 'बालकः', 'सूक्तिः', 'कस्मै धेनुः'
            ],
            'Computer Science': [
                'Python Advanced', 'Database Management Advanced', 'HTML Advanced', 'Networking Advanced', 'Cyber Safety', 'Java Advanced', 'C++ Advanced', 'Internet Applications Advanced', 'AI and Machine Learning Basics'
            ]
        }
    }

    # Descriptions for each subject
    subject_desc = {
        'English': 'Topic from English textbook',
        'Hindi': 'Lesson from Hindi textbook',
        'Mathematics': 'Unit from Mathematics textbook',
        'Science': 'Unit from Science textbook',
        'History': 'Chapter from History textbook',
        'Geography': 'Chapter from Geography textbook',
        'Civics': 'Chapter from Civics textbook',
        'Sanskrit': 'Lesson from Sanskrit textbook',
        'Computer Science': 'Unit from ICT/Computer Science',
    }

    # Insert all topics for Grades 6 to 12
    for grade in syllabus_data:
        board = 'Maharashtra' if grade == 6 else 'CBSE'  # Add logic for other boards as needed
        academic_year = '2025-26'
        if grade not in syllabus_data:
            continue
        for subject, topics in syllabus_data[grade].items():
            subject_desc = {}  # Optionally add subject descriptions
            for topic in topics:
                insert_syllabus(board, grade, subject, academic_year, topic, subject_desc.get(subject, ''))

    # Display all stored syllabus for CBSE Grades 6 to 12
    for grade in range(6, 13):
        print(f"\nCBSE Grade {grade} Syllabus ({academic_year}):\n")
        for subject in syllabus_data.get(grade, {}):
            results = get_syllabus(board, grade, subject, academic_year)
            print(f"{subject}:")
            for topic, desc in results:
                print(f"- {topic}: {desc}")
