import {Steps, StepStatus} from "../constants";

export function getInitData(CV=false) {

    return {
        steps: [
            {
                "name": Steps.DataCleaning.name,
                "index": 0,
                "type": Steps.DataCleaning.type,
                "status": "process",
                "configuration": {
                    "cv": CV,
                    "name": "data_clean",
                    "random_state": 9527,
                    "train_test_split_strategy": null,
                    "data_cleaner_args": {
                        "nan_chars": null,
                        "correct_object_dtype": true,
                        "drop_constant_columns": true,
                        "drop_label_nan_rows": true,
                        "drop_idness_columns": true,
                        "replace_inf_values": null,
                        "drop_columns": null,
                        "drop_duplicated_columns": false,
                        "reduce_mem_usage": false,
                        "int_convert_to": "float"
                    }
                },
                "extension": null,
                "start_datetime": "2020-11-11 22:22:22",
                "end_datetime": "2020-11-11 22:22:22"
            }
        ]
    }
}

export function sendFinishData(store, delay = 1000) {

    setTimeout(function () {
        store.dispatch(
            {
                type: 'stepFinished',
                payload: {
                    index: 0,
                    type: 'DataCleanStep',
                    extension: {unselected_reason: {"id": 'unknown'}},
                    status: StepStatus.Finish,
                    datetime: ''
                }
            })
    }, delay);
}
