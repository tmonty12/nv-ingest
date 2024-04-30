from unittest.mock import Mock

import pytest

from nv_ingest.util.flow_control.filter_by_task import filter_by_task


@pytest.fixture
def mock_control_message():
    # Create a mock ControlMessage object
    control_message = Mock()
    control_message.payload.return_value = "not processed"

    # Default to False for unspecified tasks
    control_message.has_task.return_value = False

    # To simulate has_task returning True for a specific task ("task1")
    control_message.has_task.side_effect = lambda task: task == "task1"

    # To simulate get_tasks for a specific task "task1"
    control_message.get_tasks.return_value = {"task1": [{"prop1": "foo"}]}

    return control_message


# Sample function to be decorated
def process_message(message):
    message.payload.return_value = "processed"
    return message


def test_filter_by_task_with_required_task(mock_control_message):
    decorated_func = filter_by_task(["task1"])(process_message)
    assert (
        decorated_func(mock_control_message).payload() == "processed"
    ), "Should process the message when required task is present."


def test_filter_by_task_with_required_task_properties(mock_control_message):
    decorated_func = filter_by_task([("task1", {"prop1": "foo"})])(process_message)
    assert (
        decorated_func(mock_control_message).payload() == "processed"
    ), "Should process the message when both required task and required property are present."


def test_filter_by_task_without_required_task_no_forward_func(mock_control_message):
    decorated_func = filter_by_task(["task3"])(process_message)
    assert (
        decorated_func(mock_control_message).payload() == "not processed"
    ), "Should return the original message when required task is not present and no forward_func is provided."


def test_filter_by_task_without_required_task_properteies_no_forward_func(mock_control_message):
    decorated_func = filter_by_task([("task1", {"prop1": "bar"})])(process_message)
    assert (
        decorated_func(mock_control_message).payload() == "not processed"
    ), "Should return the original message when required task is present but required task property is not present."


def test_filter_by_task_without_required_task_with_forward_func(mock_control_message):
    # Create a simple mock function to be decorated
    mock_function = Mock(return_value="some_value")

    # Setup the forward function
    forward_func = Mock(return_value=mock_control_message)

    # Apply the decorator to the mock function
    decorated_func = filter_by_task(["task3"], forward_func=forward_func)(mock_function)

    # Call the decorated function with the control message
    result = decorated_func(mock_control_message)

    # Check if forward_func was called since required task is not present
    forward_func.assert_called_once_with(mock_control_message)

    # Assert that the result of calling the decorated function is as expected
    assert result == mock_control_message, "Should return the mock_control_message from the forward function."


def test_filter_by_task_without_required_task_properties_with_forward_func(mock_control_message):
    # Create a simple mock function to be decorated
    mock_function = Mock(return_value="some_value")

    # Setup the forward function
    forward_func = Mock(return_value=mock_control_message)

    # Apply the decorator to the mock function
    decorated_func = filter_by_task([("task1", {"prop1": "bar"})], forward_func=forward_func)(mock_function)

    # Call the decorated function with the control message
    result = decorated_func(mock_control_message)

    # Check if forward_func was called since required task is not present
    forward_func.assert_called_once_with(mock_control_message)

    # Assert that the result of calling the decorated function is as expected
    assert result == mock_control_message, "Should return the mock_control_message from the forward function."


def test_filter_by_task_with_invalid_argument():
    decorated_func = filter_by_task(["task1"])(process_message)
    with pytest.raises(ValueError):
        decorated_func(
            "not a ControlMessage"
        ), "Should raise ValueError if the first argument is not a ControlMessage object."
