/*
 * @author        :: Preston Wang-Stosur-Bassett
 * @date          :: October 8, 2020
 * @description   :: This package returns the hsk level for a simplified chinese character
 */

use std::collections::HashMap;
use bincode::deserialize_from;

static HSK_DATA: &'static [u8] = include_bytes!("../data/hsk.data");

pub struct Hsk {
    hsk_map: HashMap<String, u8>
}

impl Hsk {
    pub fn new() -> Hsk {
        return Hsk {
            hsk_map: deserialize_from(HSK_DATA).unwrap()
        }
    }
    
    pub fn get_hsk(&self, character: &str) -> u8 {
        return match self.hsk_map.get(character) {
            Some(hsk_level) => *hsk_level,
            None => 0
        }
    }
}