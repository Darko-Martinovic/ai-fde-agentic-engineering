import type { ModelAllowed } from "../api";
import { Panel } from "./elements";

/** A price per million tokens, such as $0.10. */
function perMillion(price: number): string {
  return `$${price.toFixed(2)}`;
}

/** The models the claim agent may use, set in data/models.json: read only. */
export function ModelsAllowed({
  models,
}: Readonly<{ models: ModelAllowed[] }>) {
  return (
    <Panel title="Models the claim agent may use">
      <p className="muted">
        Set in data/models.json and can&apos;t be changed here. Prices are in US
        dollars per million tokens.
      </p>
      <div className="table-scroll">
        <table className="data-table" aria-label="Models allowed">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Reasoning efforts</th>
              <th scope="col" className="numeric">
                Input
              </th>
              <th scope="col" className="numeric">
                Output
              </th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.model}>
                <td>
                  {model.label}
                  <span className="muted mono"> {model.model}</span>
                </td>
                <td>{model.reasoning_efforts.join(", ")}</td>
                <td className="numeric">{perMillion(model.input_price)}</td>
                <td className="numeric">{perMillion(model.output_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
