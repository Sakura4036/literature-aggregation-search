# Literature Data Models

This module provides standardized data models and schemas for literature information, based on the database design in `docs/database_design.md`.

## Overview

The literature data models provide a unified way to represent academic literature from multiple sources (PubMed, ArXiv, Semantic Scholar, Web of Science, bioRxiv) with consistent data structures, validation, and serialization capabilities.

## Core Components

### Enumerations (`enums.py`)

- **IdentifierType**: Types of article identifiers (DOI, PMID, ArXiv ID, etc.)
- **VenueType**: Types of publication venues (journal, conference, preprint server, etc.)
- **CategoryType**: Types of subject categories (MeSH, ArXiv categories, fields of study, etc.)
- **PublicationTypeSource**: Sources of publication type information

### Schema Classes (`schemas.py`)

#### ArticleSchema
Represents basic article information:
- Title, abstract, language
- Publication dates and year
- Citation and reference counts
- Open access information

#### AuthorSchema
Represents author information:
- Names (full, last, fore, initials)
- ORCID and other identifiers
- Affiliation and correspondence status
- Author order

#### VenueSchema
Represents publication venue information:
- Venue name and type
- ISSN numbers (print and electronic)
- Publisher and country information

#### PublicationSchema
Represents publication details:
- Volume, issue, page information
- Article numbers

#### IdentifierSchema
Represents article identifiers:
- Identifier type and value
- Primary identifier flag

#### CategorySchema
Represents subject categories:
- Category name, code, and type
- Major topic flag and confidence score

#### PublicationTypeSchema
Represents publication types:
- Type name, code, and source

#### LiteratureSchema
The main unified schema that combines all components:
- Article, authors, venue, and publication information
- Lists of identifiers, categories, and publication types
- Source-specific data storage
- Validation and serialization methods

## Key Features

### Data Validation
```python
literature = LiteratureSchema()
literature.article.title = "Sample Article"
literature.article.primary_doi = "10.1000/test"

is_valid, errors = literature.validate()
if not is_valid:
    print("Validation errors:", errors)
```

### Identifier Management
```python
# Add identifiers
literature.add_identifier(IdentifierType.DOI, "10.1000/test", is_primary=True)
literature.add_identifier(IdentifierType.PMID, "12345678")

# Get identifiers
doi = literature.get_doi()
pmid = literature.get_pmid()
```

### Author Management
```python
# Add authors
literature.add_author("John Doe", orcid="0000-0000-0000-0000", is_corresponding=True)
literature.add_author("Jane Smith", affiliation="University of Example")
```

### Serialization
```python
# Convert to dictionary
data = literature.to_dict()

# Create from dictionary
literature = LiteratureSchema.from_dict(data)
```

## Usage Examples

### Creating a Literature Record
```python
from src.models import LiteratureSchema, IdentifierType, VenueType

# Create new literature record
literature = LiteratureSchema()

# Set article information
literature.article.title = "Machine Learning in Healthcare"
literature.article.abstract = "This paper explores ML applications in healthcare."
literature.article.publication_year = 2023

# Add authors
literature.add_author("Dr. Smith", is_corresponding=True)
literature.add_author("Prof. Johnson")

# Set venue
literature.venue.venue_name = "Nature Medicine"
literature.venue.venue_type = VenueType.JOURNAL

# Add identifiers
literature.add_identifier(IdentifierType.DOI, "10.1038/s41591-023-01234-5")

# Validate
is_valid, errors = literature.validate()
```

### Working with Existing Data
```python
from src.search.response_formatter import ResponseFormatter

# Format data from search API
pubmed_data = {...}  # Raw PubMed data
formatted_data = ResponseFormatter.format_pubmed(pubmed_data)

# Create schema from formatted data
literature = LiteratureSchema.from_dict(formatted_data)

# Access information
print(f"Title: {literature.article.title}")
print(f"Authors: {[author.full_name for author in literature.authors]}")
print(f"DOI: {literature.get_doi()}")
```

## Integration with Existing Systems

The schema classes are designed to work seamlessly with the existing response formatter and search APIs:

1. **Response Formatter Integration**: The `LiteratureSchema.from_dict()` method can directly consume output from `ResponseFormatter.format_*()` methods.

2. **Backward Compatibility**: The schema classes don't break existing functionality - they provide an additional layer of standardization.

3. **Validation**: Built-in validation ensures data quality and consistency across different sources.

4. **Extensibility**: Easy to add new identifier types, venue types, or category types as needed.

## Testing

Comprehensive unit tests are provided in `tests/test_models/`:

- `test_enums.py`: Tests for enumeration types
- `test_schemas.py`: Tests for schema classes
- `test_integration.py`: Integration tests with existing systems

Run tests with:
```bash
python -m pytest tests/test_models/ -v
```

## Future Enhancements

The schema classes are designed to support future enhancements:

1. **Additional Validation Rules**: More sophisticated validation logic
2. **Custom Serialization**: Support for different output formats (JSON, XML, etc.)
3. **Database Integration**: Direct ORM mapping capabilities
4. **Performance Optimization**: Caching and lazy loading for large datasets