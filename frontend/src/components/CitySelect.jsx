export default function CitySelect({ value, onChange }) {
  return (
    <label className="city-select">
      <span>当前城市</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete="address-level2"
      />
    </label>
  );
}
