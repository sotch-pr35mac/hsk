/*
 * @author		:: Preston Wang-Stosur-Bassett <p.wanstobas@gmail.com>
 * @date		:: October 8, 2020
 * @description	:: Return HSK Level for Simplified Chinese Characters
*/

//! ### About
//! Return HSK Level for Simplified Chinese Characters
//! 
//! ### Usage
//! ```rust
//! extern crate hsk;
//! 
//! use hsk::Hsk;
//! 
//! fn main() {
//! 	let hsk_list = Hsk::new();
//! 	let character: &str = "成为";
//! 	let result: u8 = hsk_list.get_hsk(character);
//! 	println!("{:?}", result); // --> 4
//! }
//! ```

extern crate bincode;

mod hsk;
pub use self::hsk::Hsk as Hsk;

#[cfg(test)]
mod tests {
	use super::*;
	
	#[test]
	fn test_no_hsk() {
		let	hsk = Hsk::new();
		let character: &str = "你好";
		let expected: u8 = 0;
		let actual: u8 = hsk.get_hsk(character);
		assert_eq!(expected, actual);
	}
	
	#[test]
	fn test_hsk_1() {
		let hsk = Hsk::new();
		let character: &str = "飞机";
		let expected: u8 = 1;
		let actual: u8 = hsk.get_hsk(character);
		assert_eq!(expected, actual);
	}
	
	#[test]
	fn test_hsk_2() {
		let hsk = Hsk::new();
		let character: &str = "火车站";
		let expected: u8 = 2;
		let actual: u8 = hsk.get_hsk(character);
		assert_eq!(expected, actual);
	}
	
	#[test]
	fn test_hsk_3() {
		let hsk = Hsk::new();
		let character: &str = "地方";
		let expected: u8 = 3;
		let actual: u8 = hsk.get_hsk(character);
		assert_eq!(expected, actual);
	}
	
	#[test]
	fn test_hsk_4() {
		let hsk = Hsk::new();
		let character: &str = "成为";
		let expected: u8 = 4;
		let actual: u8 = hsk.get_hsk(character);
		assert_eq!(expected, actual);
	}
	
	#[test]
	fn test_hsk_5() {
		let hsk = Hsk::new();
		let character: &str = "本科";
		let expected: u8 = 5;
		let actual: u8 = hsk.get_hsk(character);
		assert_eq!(expected, actual);
	}
	
	#[test]
	fn test_hsk_6() {
		let hsk = Hsk::new();
		let character: &str = "版本";
		let expected: u8 = 6;
		let actual: u8 = hsk.get_hsk(character);
		assert_eq!(expected, actual);
	}	
}
