# hsk
### About
Return HSK Level for Simplified Chinese Characters

### Usage
```rust
extern crate hsk;

use hsk::Hsk;

fn main() {
	let hsk_list = Hsk::new();
	let character: &str = "成为";
	let result: u8 = hsk_list.hsk(character);
	println!("{:?}", result); // --> 4
}
```

### Contributors
- [Preston Wang-Stosur-Bassett](http://stosur.info)

### License
[MIT](https://github.com/sotch-pr35mac/hsk/blob/master/LICENSE)
