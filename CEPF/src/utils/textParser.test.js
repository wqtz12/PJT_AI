const { removeDuplicates } = require('./textParser');

describe('textParser', () => {
  describe('removeDuplicates', () => {
    it('should remove duplicate strings based on similarity', () => {
      const texts = [
        'hello world',
        'hello world!', // similar to 'hello world'
        'foo bar',
        'foo bar baz',
        'a completely different string',
      ];
      const uniqueTexts = removeDuplicates(texts, 0.8);
      expect(uniqueTexts).toEqual([
        'hello world',
        'foo bar',
        'foo bar baz',
        'a completely different string',
      ]);
    });

    it('should not remove strings if they are not similar enough', () => {
        const texts = [
            'hello world',
            'goodbye world',
            'foo bar',
        ];
        const uniqueTexts = removeDuplicates(texts, 0.8);
        expect(uniqueTexts).toEqual(texts);
    });
  });
});
