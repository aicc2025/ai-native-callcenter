"""Guideline definition loader from YAML files."""
from pathlib import Path
from typing import Dict, List, Any, Optional
from uuid import UUID
import yaml

from app.flow_control.guideline.models import Guideline, GuidelineScope
from app.logging_config import get_logger
from uuid7 import uuid7

logger = get_logger(__name__)


class GuidelineValidationError(Exception):
    """Raised when guideline definition validation fails."""
    pass


class GuidelineLoader:
    """Loads and validates guideline definitions from YAML files."""

    @staticmethod
    def load_from_yaml(file_path: Path) -> Dict[str, Any]:
        """
        Load guideline definitions from YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Dictionary with guideline definitions

        Raises:
            GuidelineValidationError: If YAML is invalid
        """
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                raise GuidelineValidationError(f"Empty YAML file: {file_path}")

            return data

        except yaml.YAMLError as e:
            raise GuidelineValidationError(f"Invalid YAML in {file_path}: {e}")
        except FileNotFoundError:
            raise GuidelineValidationError(f"File not found: {file_path}")

    @staticmethod
    def validate_guideline_schema(data: Dict[str, Any]) -> None:
        """
        Validate guideline data structure.

        Args:
            data: Guideline definition dictionary

        Raises:
            GuidelineValidationError: If validation fails
        """
        required_fields = ['name', 'scope', 'condition', 'action']

        for field in required_fields:
            if field not in data:
                raise GuidelineValidationError(f"Missing required field: {field}")

        # Validate scope
        valid_scopes = ['GLOBAL', 'JOURNEY', 'STATE']
        if data['scope'] not in valid_scopes:
            raise GuidelineValidationError(
                f"Invalid scope '{data['scope']}'. Must be one of: {valid_scopes}"
            )

        # Validate scope-specific requirements
        if data['scope'] == 'JOURNEY' and 'journey_name' not in data:
            raise GuidelineValidationError("JOURNEY scope requires journey_name field")

        if data['scope'] == 'STATE':
            if 'journey_name' not in data:
                raise GuidelineValidationError("STATE scope requires journey_name field")
            if 'state_name' not in data:
                raise GuidelineValidationError("STATE scope requires state_name field")

        # Validate keywords if present
        if 'keywords' in data and not isinstance(data['keywords'], list):
            raise GuidelineValidationError("keywords must be a list")

        # Validate tools if present
        if 'tools' in data and not isinstance(data['tools'], list):
            raise GuidelineValidationError("tools must be a list")

        # Validate priority if present
        if 'priority' in data and not isinstance(data['priority'], int):
            raise GuidelineValidationError("priority must be an integer")

    @staticmethod
    async def parse_guideline(
        data: Dict[str, Any],
        journey_id_map: Dict[str, UUID],
        guideline_id: Optional[UUID] = None,
    ) -> Guideline:
        """
        Parse validated data into Guideline model.

        Args:
            data: Validated guideline definition dictionary
            journey_id_map: Mapping of journey names to UUIDs
            guideline_id: Optional UUID to use

        Returns:
            Guideline model instance

        Raises:
            GuidelineValidationError: If journey_name doesn't exist in map
        """
        scope = GuidelineScope(data['scope'])

        # Resolve journey_id from journey_name if needed
        journey_id = None
        if scope in [GuidelineScope.JOURNEY, GuidelineScope.STATE]:
            journey_name = data.get('journey_name')
            if journey_name not in journey_id_map:
                raise GuidelineValidationError(
                    f"Journey '{journey_name}' not found in database"
                )
            journey_id = journey_id_map[journey_name]

        guideline = Guideline(
            id=guideline_id or uuid7(),
            scope=scope,
            name=data['name'],
            description=data.get('description'),
            condition=data['condition'],
            action=data['action'],
            keywords=data.get('keywords', []),
            tools=data.get('tools', []),
            priority=data.get('priority', 0),
            enabled=data.get('enabled', True),
            journey_id=journey_id,
            state_name=data.get('state_name'),
        )

        return guideline

    @staticmethod
    async def load_guidelines_from_file(
        file_path: Path,
        journey_id_map: Dict[str, UUID],
    ) -> List[Guideline]:
        """
        Load and parse guidelines from YAML file.

        Args:
            file_path: Path to YAML file
            journey_id_map: Mapping of journey names to UUIDs

        Returns:
            List of Guideline model instances

        Raises:
            GuidelineValidationError: If loading or validation fails
        """
        logger.info("Loading guidelines from file", file_path=str(file_path))

        # Load YAML
        data = GuidelineLoader.load_from_yaml(file_path)

        # Expect a 'guidelines' key with list of guidelines
        if 'guidelines' not in data:
            raise GuidelineValidationError(
                f"YAML file must contain 'guidelines' list: {file_path}"
            )

        if not isinstance(data['guidelines'], list):
            raise GuidelineValidationError(
                f"'guidelines' must be a list: {file_path}"
            )

        guidelines = []
        for i, guideline_data in enumerate(data['guidelines']):
            try:
                # Validate schema
                GuidelineLoader.validate_guideline_schema(guideline_data)

                # Parse into model
                guideline = await GuidelineLoader.parse_guideline(
                    guideline_data,
                    journey_id_map,
                )
                guidelines.append(guideline)

            except GuidelineValidationError as e:
                logger.error(
                    "Failed to load guideline",
                    file_path=str(file_path),
                    index=i,
                    error=str(e),
                )
                raise GuidelineValidationError(
                    f"Error in guideline {i} of {file_path}: {e}"
                )

        logger.info(
            "Guidelines loaded successfully",
            file_path=str(file_path),
            count=len(guidelines),
        )

        return guidelines

    @staticmethod
    async def load_guidelines_from_directory(
        directory: Path,
        journey_id_map: Dict[str, UUID],
    ) -> List[Guideline]:
        """
        Load all guideline YAML files from a directory.

        Args:
            directory: Path to directory containing YAML files
            journey_id_map: Mapping of journey names to UUIDs

        Returns:
            List of Guideline model instances
        """
        if not directory.exists():
            raise GuidelineValidationError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise GuidelineValidationError(f"Not a directory: {directory}")

        all_guidelines = []
        yaml_files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))

        if not yaml_files:
            logger.warning("No YAML files found in directory", directory=str(directory))
            return all_guidelines

        for file_path in yaml_files:
            try:
                guidelines = await GuidelineLoader.load_guidelines_from_file(
                    file_path,
                    journey_id_map,
                )
                all_guidelines.extend(guidelines)
            except GuidelineValidationError as e:
                logger.error(
                    "Failed to load guidelines from file",
                    file_path=str(file_path),
                    error=str(e),
                )
                raise

        logger.info(
            "Loaded guidelines from directory",
            directory=str(directory),
            total_count=len(all_guidelines),
        )

        return all_guidelines

    @staticmethod
    def to_db_format(guideline: Guideline) -> Dict[str, Any]:
        """
        Convert Guideline model to database-compatible format.

        Args:
            guideline: Guideline model instance

        Returns:
            Dictionary ready for database insertion
        """
        return {
            'id': guideline.id,
            'scope': guideline.scope.value,
            'journey_id': guideline.journey_id,
            'state_name': guideline.state_name,
            'name': guideline.name,
            'description': guideline.description,
            'condition': guideline.condition,
            'action': guideline.action,
            'tools': guideline.tools,
            'keywords': guideline.keywords,
            'priority': guideline.priority,
            'enabled': guideline.enabled,
        }
