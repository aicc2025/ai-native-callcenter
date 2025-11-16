"""Journey definition loader from YAML files."""
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

from app.flow_control.journey.models import Journey, JourneyState, JourneyTransition
from app.logging_config import get_logger
from uuid7 import uuid7
from uuid import UUID

logger = get_logger(__name__)


class JourneyValidationError(Exception):
    """Raised when journey definition validation fails."""
    pass


class JourneyLoader:
    """Loads and validates journey definitions from YAML files."""

    @staticmethod
    def load_from_yaml(file_path: Path) -> Dict[str, Any]:
        """
        Load journey definition from YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Dictionary with journey definition data

        Raises:
            JourneyValidationError: If YAML is invalid or missing required fields
        """
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                raise JourneyValidationError(f"Empty YAML file: {file_path}")

            return data

        except yaml.YAMLError as e:
            raise JourneyValidationError(f"Invalid YAML in {file_path}: {e}")
        except FileNotFoundError:
            raise JourneyValidationError(f"File not found: {file_path}")

    @staticmethod
    def validate_journey_schema(data: Dict[str, Any]) -> None:
        """
        Validate journey data structure.

        Args:
            data: Journey definition dictionary

        Raises:
            JourneyValidationError: If validation fails
        """
        required_fields = ['name', 'activation_conditions', 'initial_state', 'states', 'transitions']

        for field in required_fields:
            if field not in data:
                raise JourneyValidationError(f"Missing required field: {field}")

        # Validate name
        if not isinstance(data['name'], str) or not data['name'].strip():
            raise JourneyValidationError("Field 'name' must be a non-empty string")

        # Validate activation_conditions
        if not isinstance(data['activation_conditions'], str) or not data['activation_conditions'].strip():
            raise JourneyValidationError("Field 'activation_conditions' must be a non-empty string")

        # Validate initial_state
        if not isinstance(data['initial_state'], str) or not data['initial_state'].strip():
            raise JourneyValidationError("Field 'initial_state' must be a non-empty string")

        # Validate states
        if not isinstance(data['states'], dict) or not data['states']:
            raise JourneyValidationError("Field 'states' must be a non-empty dictionary")

        # Validate initial state exists in states
        if data['initial_state'] not in data['states']:
            raise JourneyValidationError(
                f"Initial state '{data['initial_state']}' not found in states"
            )

        # Validate each state
        for state_name, state_data in data['states'].items():
            JourneyLoader._validate_state(state_name, state_data)

        # Validate transitions
        if not isinstance(data['transitions'], list):
            raise JourneyValidationError("Field 'transitions' must be a list")

        # Validate each transition
        state_names = set(data['states'].keys())
        for i, transition in enumerate(data['transitions']):
            JourneyLoader._validate_transition(i, transition, state_names)

    @staticmethod
    def _validate_state(state_name: str, state_data: Dict[str, Any]) -> None:
        """Validate individual state configuration."""
        if not isinstance(state_data, dict):
            raise JourneyValidationError(f"State '{state_name}' must be a dictionary")

        required_fields = ['name', 'action']
        for field in required_fields:
            if field not in state_data:
                raise JourneyValidationError(f"State '{state_name}' missing required field: {field}")

        if state_data['name'] != state_name:
            raise JourneyValidationError(
                f"State name mismatch: key is '{state_name}' but name field is '{state_data['name']}'"
            )

        if not isinstance(state_data['action'], str) or not state_data['action'].strip():
            raise JourneyValidationError(f"State '{state_name}' action must be a non-empty string")

        # Tools is optional but must be a list if present
        if 'tools' in state_data:
            if not isinstance(state_data['tools'], list):
                raise JourneyValidationError(f"State '{state_name}' tools must be a list")

    @staticmethod
    def _validate_transition(index: int, transition: Dict[str, Any], valid_states: set) -> None:
        """Validate individual transition configuration."""
        if not isinstance(transition, dict):
            raise JourneyValidationError(f"Transition {index} must be a dictionary")

        required_fields = ['from_state', 'to_state', 'condition']
        for field in required_fields:
            if field not in transition:
                raise JourneyValidationError(f"Transition {index} missing required field: {field}")

        # Validate states exist
        if transition['from_state'] not in valid_states:
            raise JourneyValidationError(
                f"Transition {index} from_state '{transition['from_state']}' not found in states"
            )

        if transition['to_state'] not in valid_states:
            raise JourneyValidationError(
                f"Transition {index} to_state '{transition['to_state']}' not found in states"
            )

        # Validate condition
        if not isinstance(transition['condition'], str) or not transition['condition'].strip():
            raise JourneyValidationError(f"Transition {index} condition must be a non-empty string")

        # Priority is optional but must be an integer if present
        if 'priority' in transition:
            if not isinstance(transition['priority'], int):
                raise JourneyValidationError(f"Transition {index} priority must be an integer")

    @staticmethod
    def parse_journey(
        data: Dict[str, Any],
        journey_id: Optional[UUID] = None
    ) -> Journey:
        """
        Parse validated data into Journey model.

        Args:
            data: Validated journey definition dictionary
            journey_id: Optional UUID to use (generates new one if not provided)

        Returns:
            Journey model instance
        """
        # Parse states
        states = {}
        for state_name, state_data in data['states'].items():
            states[state_name] = JourneyState(
                name=state_data['name'],
                action=state_data['action'],
                tools=state_data.get('tools', []),
                metadata=state_data.get('metadata', {}),
            )

        # Parse transitions
        transitions = []
        for transition_data in data['transitions']:
            transitions.append(
                JourneyTransition(
                    from_state=transition_data['from_state'],
                    to_state=transition_data['to_state'],
                    condition=transition_data['condition'],
                    priority=transition_data.get('priority', 0),
                )
            )

        # Create Journey
        journey = Journey(
            id=journey_id or uuid7(),
            name=data['name'],
            description=data.get('description'),
            activation_conditions=data['activation_conditions'],
            initial_state=data['initial_state'],
            states=states,
            transitions=transitions,
            enabled=data.get('enabled', True),
        )

        return journey

    @staticmethod
    def load_journey_from_file(
        file_path: Path,
        journey_id: Optional[UUID] = None
    ) -> Journey:
        """
        Load and parse journey from YAML file.

        Args:
            file_path: Path to YAML file
            journey_id: Optional UUID to use

        Returns:
            Journey model instance

        Raises:
            JourneyValidationError: If loading or validation fails
        """
        logger.info("Loading journey from file", file_path=str(file_path))

        # Load YAML
        data = JourneyLoader.load_from_yaml(file_path)

        # Validate schema
        JourneyLoader.validate_journey_schema(data)

        # Parse into model
        journey = JourneyLoader.parse_journey(data, journey_id)

        logger.info(
            "Journey loaded successfully",
            journey_name=journey.name,
            states_count=len(journey.states),
            transitions_count=len(journey.transitions),
        )

        return journey

    @staticmethod
    def load_journeys_from_directory(directory: Path) -> List[Journey]:
        """
        Load all journey YAML files from a directory.

        Args:
            directory: Path to directory containing YAML files

        Returns:
            List of Journey model instances
        """
        if not directory.exists():
            raise JourneyValidationError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise JourneyValidationError(f"Not a directory: {directory}")

        journeys = []
        yaml_files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))

        if not yaml_files:
            logger.warning("No YAML files found in directory", directory=str(directory))
            return journeys

        for file_path in yaml_files:
            try:
                journey = JourneyLoader.load_journey_from_file(file_path)
                journeys.append(journey)
            except JourneyValidationError as e:
                logger.error(
                    "Failed to load journey",
                    file_path=str(file_path),
                    error=str(e),
                )
                raise

        logger.info(
            "Loaded journeys from directory",
            directory=str(directory),
            count=len(journeys),
        )

        return journeys

    @staticmethod
    def to_db_format(journey: Journey) -> Dict[str, Any]:
        """
        Convert Journey model to database-compatible format.

        Args:
            journey: Journey model instance

        Returns:
            Dictionary ready for database insertion
        """
        return {
            'id': journey.id,
            'name': journey.name,
            'description': journey.description,
            'activation_conditions': journey.activation_conditions,
            'initial_state': journey.initial_state,
            'states': {
                name: {
                    'name': state.name,
                    'action': state.action,
                    'tools': state.tools,
                    'metadata': state.metadata,
                }
                for name, state in journey.states.items()
            },
            'transitions': [
                {
                    'from_state': t.from_state,
                    'to_state': t.to_state,
                    'condition': t.condition,
                    'priority': t.priority,
                }
                for t in journey.transitions
            ],
            'enabled': journey.enabled,
        }
