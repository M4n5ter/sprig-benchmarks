//! Source-only public-encoder proof; no Store, daemon, socket, mount or workload.
use layerfs_bridge::control::{Answer, ControlError, Reply, SdkValue};

include!("fixture.rs");

fn encoded_size(value: &SdkValue) -> usize {
    match value {
        SdkValue::Null | SdkValue::Bool(_) => 1,
        SdkValue::Int(_) => 9,
        SdkValue::Text(value) => 5 + value.len(),
        SdkValue::Bytes(value) => 5 + value.len(),
        SdkValue::List(values) => 5 + values.iter().map(encoded_size).sum::<usize>(),
        SdkValue::Map(fields) => 5 + fields.iter()
            .map(|(name, value)| 2 + name.len() + encoded_size(value)).sum::<usize>(),
    }
}

fn answer(value: SdkValue) -> Answer {
    Answer { id: 810, reply: Reply::Sdk(value) }
}

fn main() {
    // Independent scalar controls hold the actual unmodified encoder boundary.
    let small = answer(SdkValue::Text("ordinary encoder control".to_owned()));
    let bytes = small.encode().expect("small public answer must encode");
    assert_eq!(Answer::decode(&bytes).expect("small answer decodes"), small);
    // LFSA-v2 magic5 + id8 + Sdk tag1 + Bytes tag1 + u32 length4 =19.
    let boundary = answer(SdkValue::Bytes(vec![0; 65_519 - 19]));
    let bytes = boundary.encode().expect("exact fixed limit must encode");
    assert_eq!(bytes.len(), 65_519);
    assert_eq!(Answer::decode(&bytes).expect("boundary answer decodes"), boundary);
    assert_eq!(answer(SdkValue::Bytes(vec![0; 65_519 - 18])).encode(),
               Err(ControlError("control record limit")));

    for observed_mask in 0..8 {
        let value = reconstructed_subset(observed_mask);
        let predicted = 14 + encoded_size(&value);
        assert_eq!(predicted, EXPECTED_SUBSET_ANSWER_BYTES[observed_mask]);
        assert!(predicted > 65_519);
        // This is the exact public product encoder, not the size model.
        assert_eq!(answer(value).encode(), Err(ControlError("control record limit")));
        println!("model_case={observed_mask} predicted_subset_answer_bytes={predicted} actual_encoder=control_record_limit");
    }
    println!("proof=passed source_identity=external_preflight_required captured_daemon_receipt=false mounted_run=false");
}
