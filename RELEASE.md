# Release Process

Sample release process, in this example we're releasing `1.0.20`.

1. **Versioning**
   ```bash
   sed -i '' 's/"version": "[^"]*"/"version": "1.0.20"/' custom_components/hkc_alarm/manifest.json
      sed -i '' 's/"hacs": "[^"]*"/"hacs": "1.0.20"/' hacs.json
   ```

2. **Tag**
   ```bash
   git tag 1.0.20
   git push origin 1.0.20
   ```

3. **Create GitHub Release**
   - Go to https://github.com/jasonmadigan/ha-hkc/releases
   - Click "Create a new release"
   - Select the tag created above
   - Add release notes
   - Publish release
